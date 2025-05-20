from rasa.core.agent import Agent
import asyncio
import os
import pandas as pd
from rouge_score import rouge_scorer
from bert_score import score as bert_score_calculate
import torch
from tqdm import tqdm

# --- RASA Interaction Functions ---
async def get_rasa_bot_response_async(text_to_process, agent):
    if not agent:
        print("Agent not loaded.")
        return "[AGENT_NOT_LOADED]"
    
    bot_messages = await agent.handle_text(text_to_process)
    
    if bot_messages:
        responses = [msg.get("text") for msg in bot_messages if msg.get("text")]
        if responses:
            return " ".join(responses)
        else:
            return "[NO_TEXTUAL_RESPONSE]"
    else:
        return "[NO_BOT_RESPONSE]"

# --- Scoring Functions ---
def calculate_simplified_rouge_scores(reference, hypothesis, scorer_instance):
    if not reference or not hypothesis or reference.isspace() or hypothesis.isspace():
        return {
            'rouge1_fmeasure': 0.0,
            'rouge2_fmeasure': 0.0,
            'rougeL_fmeasure': 0.0,
        }
    try:
        scores = scorer_instance.score(reference, hypothesis)
        return {
            'rouge1_fmeasure': scores['rouge1'].fmeasure,
            'rouge2_fmeasure': scores['rouge2'].fmeasure,
            'rougeL_fmeasure': scores['rougeL'].fmeasure,
        }
    except ValueError:
         return {
            'rouge1_fmeasure': 0.0,
            'rouge2_fmeasure': 0.0,
            'rougeL_fmeasure': 0.0,
        }

def calculate_simplified_bertscore(references, hypotheses, lang="en", model_type=None, device=None):
    # Ensure references and hypotheses are lists and handle empty or whitespace-only strings
    # by replacing them with a single space to avoid errors with BERTScore.
    # BERTScore can be sensitive to truly empty strings.
    
    processed_refs = [ref if ref and not ref.isspace() else " " for ref in references]
    processed_hyps = [hyp if hyp and not hyp.isspace() else " " for hyp in hypotheses]

    if not any(r.strip() for r in processed_refs) or not any(h.strip() for h in processed_hyps):
        return {'bertscore_f1': 0.0}
    
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
    
    try:
        P, R, F1 = bert_score_calculate(
            processed_hyps, processed_refs, lang=lang, model_type=model_type, device=device, verbose=False
        )
        return {
            'bertscore_f1': F1.mean().item(),
        }
    except Exception as e: # Catch any exception from bert_score
        print(f"BERTScore calculation error: {e}. Inputs: Hyps='{hypotheses}', Refs='{references}'")
        return {'bertscore_f1': 0.0}


async def main():
    model_directory = "models"
    input_csv_path = "rouge_bert.csv" 
    output_csv_path = "rouge_bert_simplified_response.csv"
    
    expected_response_column_name = "Predicted Bot Response" 

    # --- Load RASA Agent ---
    if not os.path.exists(model_directory) or not os.listdir(model_directory):
        print(f"Model directory '{model_directory}' not found or is empty. Please train a model first using 'rasa train'.")
        return

    print(f"Loading agent from directory: {model_directory}")
    agent = None
    try:
        agent = Agent.load(model_path=model_directory) # Tries to find latest model in dir
        print("Agent loaded successfully.")
    except Exception as e:
        print(f"Error loading agent: {e}")
        print("Ensure a trained model exists in 'models/' and you are running from the project root.")
        return

    # --- Load CSV ---
    if not os.path.exists(input_csv_path):
        print(f"CSV file not found at '{input_csv_path}'.")
        return

    try:
        df = pd.read_csv(input_csv_path)
        print(f"\nSuccessfully loaded {len(df)} rows from {input_csv_path}")
    except Exception as e:
        print(f"Error reading CSV file '{input_csv_path}': {e}")
        return

    if 'UserInput (Clean)' not in df.columns:
        print(f"CSV file '{input_csv_path}' must contain 'UserInput (Clean)'.")
        return
    if expected_response_column_name not in df.columns:
        print(f"CSV file '{input_csv_path}' must contain '{expected_response_column_name}'.")
        return

    # --- Initialize Scorers ---
    rouge_types = ['rouge1', 'rouge2', 'rougeL']
    rouge_scorer_instance = rouge_scorer.RougeScorer(rouge_types, use_stemmer=True)
    
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Using device: {device} for BERTScore calculations.")

    results_data = []

    print("\n--- Processing User Inputs and Calculating Scores ---")
    for index, row in tqdm(df.iterrows(), total=df.shape[0], desc="Processing rows"):
        user_input_text = str(row['UserInput (Clean)'])
        expected_bot_response_text = str(row[expected_response_column_name]) if pd.notna(row[expected_response_column_name]) else ""

        if not user_input_text or pd.isna(user_input_text):
            # Add a row with NaNs or placeholders
            results_data.append({**row.to_dict(), 'Newly_Generated_Bot_Response': '[SKIPPED_EMPTY_INPUT]', 
                                 **calculate_simplified_rouge_scores("", "", rouge_scorer_instance), 
                                 **calculate_simplified_bertscore([""], [""] , device=device)})
            continue
        
        newly_generated_bot_response_text = await get_rasa_bot_response_async(user_input_text, agent)

        rouge_scores = calculate_simplified_rouge_scores(expected_bot_response_text, newly_generated_bot_response_text, rouge_scorer_instance)
        
        # Handle placeholders for BERTScore calculation
        if newly_generated_bot_response_text.startswith("[") and newly_generated_bot_response_text.endswith("]"):
            current_bert_scores = calculate_simplified_bertscore([expected_bot_response_text], [" "], device=device) # Treat placeholder as empty
        else:
            current_bert_scores = calculate_simplified_bertscore([expected_bot_response_text], [newly_generated_bot_response_text], device=device)
        
        current_row_output = row.to_dict()
        current_row_output['Newly_Generated_Bot_Response'] = newly_generated_bot_response_text
        current_row_output.update(rouge_scores)
        current_row_output.update(current_bert_scores)
        results_data.append(current_row_output)

    # --- Create and Save Output CSV ---
    output_df = pd.DataFrame(results_data)
    
    print("\n--- Average Scores ---")
    avg_scores = {}
    # Only average the F-measures for ROUGE and BERTScore F1
    score_cols_to_average = ['rouge1_fmeasure', 'rouge2_fmeasure', 'rougeL_fmeasure', 'bertscore_f1']
    for col in score_cols_to_average:
        if col in output_df.columns: # Check if column exists
            avg_scores[f'avg_{col}'] = pd.to_numeric(output_df[col], errors='coerce').mean()
            print(f"Average {col}: {avg_scores[f'avg_{col}']:.4f}")

    try:
        output_df.to_csv(output_csv_path, index=False)
        print(f"\nEvaluation scores saved to '{output_csv_path}'")
    except Exception as e:
        print(f"Error saving output CSV to '{output_csv_path}': {e}")

if __name__ == "__main__":
    asyncio.run(main())