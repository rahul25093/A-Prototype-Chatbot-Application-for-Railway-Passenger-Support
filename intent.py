from rasa.core.agent import Agent
import asyncio
import os
import json
import pandas as pd # For reading CSV
from sklearn.metrics import confusion_matrix, accuracy_score, log_loss, roc_auc_score, classification_report
from sklearn.metrics import roc_curve, auc # Specifically for ROC curve plotting
from sklearn.preprocessing import LabelBinarizer # For binarizing labels for ROC plotting
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np # For unique labels and probability arrays
import glob # To find model files

async def get_rasa_nlu_output_async(text_to_classify, agent):
    if not agent:
        print("Agent not loaded.")
        return None
    message_data = await agent.parse_message(text_to_classify)
    return message_data

def format_rasa_output(rasa_result):
    if not rasa_result:
        return None

    formatted_entities = []
    for ent in rasa_result.get("entities", []):
        formatted_entities.append({
            "start": ent.get("start"),
            "end": ent.get("end"),
            "value": ent.get("value"),
            "entity": ent.get("entity")
        })

    intent_name = None
    intent_confidence = 0.0
    # Primary intent object
    if rasa_result.get("intent"):
        intent_name = rasa_result["intent"].get("name")
        intent_confidence = rasa_result["intent"].get("confidence", 0.0)

    # Fallback to response_selector if no primary intent (e.g. for FAQs)
    if intent_name is None and rasa_result.get("response_selector"):
        for key, selector_data in rasa_result["response_selector"].items(): # Iterate over all response selectors
            response_data = selector_data.get("response")
            if response_data and response_data.get("intent_response_key"):
                intent_name = response_data["intent_response_key"]
                # Try to get confidence from ranking within response_selector first
                ranking_in_selector = selector_data.get("ranking", [{}])
                if ranking_in_selector and isinstance(ranking_in_selector, list) and len(ranking_in_selector) > 0:
                     intent_confidence = ranking_in_selector[0].get("confidence", 0.0)
                if intent_confidence == 0.0 and response_data: # Fallback if ranking confidence is not there or zero
                    intent_confidence = response_data.get("confidence", 0.0)
                break

    # Fallback to top of intent_ranking if still no intent (should be rare if above are hit)
    if intent_name is None and rasa_result.get("intent_ranking"):
        if rasa_result["intent_ranking"]: # Ensure ranking is not empty
            intent_name = rasa_result["intent_ranking"][0].get("name")
            intent_confidence = rasa_result["intent_ranking"][0].get("confidence", 0.0)

    formatted_output = {
        "text": rasa_result.get("text"),
        "intent": intent_name if intent_name else "N/A", # Ensure "N/A" if no intent could be determined
        "confidence": intent_confidence,
        "entities": formatted_entities
    }
    return formatted_output

def find_latest_model(model_dir="models"):
    """Finds the latest .tar.gz model file in the specified directory, relative to CWD."""
    search_path = os.path.join(os.getcwd(), model_dir, '*.tar.gz')
    list_of_files = glob.glob(search_path)
    if not list_of_files:
        print(f"Debug: No .tar.gz files found in search path: {search_path}")
        return None
    latest_file = max(list_of_files, key=os.path.getctime)
    return latest_file

async def main():
    current_working_dir = os.getcwd()
    print(f"IMPORTANT: Script is running from CWD: {current_working_dir}")
    print(f"           The 'models' directory should be here: {os.path.join(current_working_dir, 'models')}")
    print(f"           The CSV file should be here: {os.path.join(current_working_dir, 'intent_accuracy.csv')}")

    model_directory_name = "models"
    csv_file_name = "intent_accuracy.csv"

    if not os.path.isdir(model_directory_name):
        print(f"ERROR: The '{model_directory_name}' directory was not found in your current working directory: {current_working_dir}")
        return

    absolute_model_path = find_latest_model(model_directory_name)
    if not absolute_model_path:
        print(f"No .tar.gz model file found in directory '{os.path.join(current_working_dir, model_directory_name)}'.")
        return
    print(f"Attempting to load agent from absolute model path: {absolute_model_path}")
    if not os.path.exists(absolute_model_path):
        print(f"FATAL: Resolved absolute model path does not exist: {absolute_model_path}")
        return

    agent = None
    try:
        agent = Agent.load(model_path=absolute_model_path)
        print("Agent loaded successfully.")
    except Exception as e:
        print(f"Error loading agent from '{absolute_model_path}': {e}")
        return

    csv_file_path = os.path.join(current_working_dir, csv_file_name)
    if not os.path.exists(csv_file_path):
        print(f"CSV file not found at '{csv_file_path}'. Please make sure the file exists in your project root.")
        return

    try:
        df = pd.read_csv(csv_file_path)
        print(f"\nSuccessfully loaded {len(df)} rows from {csv_file_path}")
    except Exception as e:
        print(f"Error reading CSV file '{csv_file_path}': {e}")
        return

    if 'UserInput' not in df.columns or 'ExpectedIntent' not in df.columns:
        print(f"CSV file '{csv_file_path}' must contain columns named 'UserInput' and 'ExpectedIntent'.")
        return

    y_true, y_pred, incorrect_predictions = [], [], []
    all_intent_rankings = [] # To store full intent_ranking list for each input
    all_top_confidences = [] # To store the confidence of the determined y_pred intent

    print("\n--- Processing User Inputs from CSV ---")
    for index, row in df.iterrows():
        user_input_text = str(row['UserInput'])
        expected_intent = str(row['ExpectedIntent'])

        if pd.isna(user_input_text) or not user_input_text.strip():
            print(f"Skipping empty UserInput at CSV row {index+2}")
            continue
        if pd.isna(expected_intent) or not expected_intent.strip():
            print(f"Skipping CSV row {index+2} due to empty ExpectedIntent for input: '{user_input_text}'")
            continue

        rasa_output = await get_rasa_nlu_output_async(user_input_text, agent)

        current_predicted_intent = "N/A"
        current_top_confidence = 0.0
        current_ranking_list = []
        confidence_for_incorrect_report = 0.0

        if rasa_output:
            simplified_output = format_rasa_output(rasa_output)
            current_predicted_intent = simplified_output.get("intent", "N/A")
            current_top_confidence = simplified_output.get("confidence", 0.0)
            current_ranking_list = rasa_output.get("intent_ranking", [])
            if not current_ranking_list and simplified_output.get("intent") != "N/A":
                 current_ranking_list = [{"name": simplified_output.get("intent"), "confidence": simplified_output.get("confidence")}]
            confidence_for_incorrect_report = current_top_confidence
        else:
            print(f"Could not get RASA NLU output for: \"{user_input_text}\" (CSV row {index+2})")
            current_predicted_intent = "NO_RASA_OUTPUT"
            current_top_confidence = 1.0
            current_ranking_list = [{"name": "NO_RASA_OUTPUT", "confidence": 1.0}]
            confidence_for_incorrect_report = 0.0

        y_true.append(expected_intent)
        y_pred.append(current_predicted_intent)
        all_top_confidences.append(current_top_confidence)
        all_intent_rankings.append(current_ranking_list)

        if expected_intent != current_predicted_intent:
            incorrect_predictions.append({
                "row_number": index + 2,
                "user_input": user_input_text,
                "expected_intent": expected_intent,
                "predicted_intent": current_predicted_intent,
                "confidence": confidence_for_incorrect_report
            })

    print("\nFinished processing CSV inputs.")

    if not y_true or not y_pred:
        print("\nNo data to calculate metrics.")
        return

    y_true_str = [str(i) for i in y_true]
    y_pred_str = [str(i) for i in y_pred]
    labels = sorted(list(set(y_true_str + y_pred_str))) # All unique labels present in true or pred
    label_to_idx = {label: i for i, label in enumerate(labels)}

    y_pred_proba = np.zeros((len(y_true_str), len(labels)))

    for i in range(len(y_true_str)):
        ranking_for_sample = all_intent_rankings[i]
        if ranking_for_sample:
            for intent_data in ranking_for_sample:
                intent_name = intent_data.get("name")
                intent_conf = intent_data.get("confidence", 0.0)
                if intent_name in label_to_idx:
                    y_pred_proba[i, label_to_idx[intent_name]] = intent_conf
        elif y_pred_str[i] in label_to_idx: # Fallback if no ranking but top prediction exists
             y_pred_proba[i, label_to_idx[y_pred_str[i]]] = all_top_confidences[i]

        row_sum = np.sum(y_pred_proba[i, :])
        if row_sum > 0:
            y_pred_proba[i, :] = y_pred_proba[i, :] / row_sum
        # else: # If row_sum is 0 (no confidences for any known label)
            # y_pred_proba[i, :] = 1.0 / len(labels) # Assign uniform probability

    print("\n--- NLU Evaluation Metrics ---")
    accuracy = accuracy_score(y_true_str, y_pred_str)
    print(f"Overall Accuracy: {accuracy * 100:.2f}%")

    print("\nClassification Report:")
    report = classification_report(y_true_str, y_pred_str, labels=labels, target_names=labels, zero_division=0)
    print(report)

    try:
        log_loss_value = log_loss(y_true_str, np.clip(y_pred_proba, 1e-15, 1 - 1e-15), labels=labels)
        print(f"Logarithmic Loss: {log_loss_value:.4f}")
    except ValueError as e:
        print(f"Could not calculate Logarithmic Loss: {e}")
        print(f"  y_pred_proba sample (first 5 rows, first 5 labels):\n{y_pred_proba[:5, :min(5, len(labels))]}")

    if len(labels) > 1:
        try:
            if len(np.unique(y_true_str)) > 1:
                 auc_score_macro_ovr = roc_auc_score(y_true_str, y_pred_proba, multi_class='ovr', average='macro', labels=labels)
                 print(f"Area Under ROC Curve (AUC) (Macro OvR): {auc_score_macro_ovr:.4f}")
            else:
                print("AUC Macro OvR calculation skipped: y_true contains only one class.")
        except ValueError as e:
            print(f"Could not calculate AUC Macro OvR: {e}")
            print(f"  y_pred_proba sample (first 5 rows, first 5 labels) after normalization:\n{y_pred_proba[:5, :min(5, len(labels))]}")
    else:
        print("AUC Macro OvR calculation skipped: Not enough classes (need at least 2).")

    if labels:
        cm = confusion_matrix(y_true_str, y_pred_str, labels=labels)
        cm_df = pd.DataFrame(cm, index=labels, columns=labels)
        print("\nConfusion Matrix:")
        print(cm_df)

        plt.figure(figsize=(max(12, len(labels)*0.6), max(10, len(labels)*0.5)))
        sns.heatmap(cm_df, annot=True, fmt='d', cmap='Blues', cbar=True)
        plt.title('Confusion Matrix: Expected vs. Predicted Intents', fontsize=16)
        plt.ylabel('Expected Intent (True)', fontsize=12)
        plt.xlabel('Predicted Intent (Actual)', fontsize=12)
        plt.xticks(rotation=45, ha='right', fontsize=10)
        plt.yticks(rotation=0, fontsize=10)
        plt.tight_layout()
        plt.savefig("confusion_matrix.png")
        print("\nConfusion matrix plot saved as confusion_matrix.png")
    else:
        print("\nNot enough distinct labels to generate a confusion matrix.")

    # --- ROC AUC Curve Plotting ---
    if len(labels) > 1 and len(np.unique(y_true_str)) > 1:
        print("\n--- ROC AUC Curve Plotting ---")
        
        lb = LabelBinarizer()
        # Fit LabelBinarizer on all possible labels to ensure consistent shape
        lb.fit(labels) 
        y_true_binarized = lb.transform(y_true_str)
        
        n_classes = len(lb.classes_) # Number of unique classes used by LabelBinarizer

        # Ensure y_pred_proba columns align with lb.classes_
        # This step is crucial if `labels` (used for y_pred_proba) and `lb.classes_` differ in order or content
        aligned_y_pred_proba = np.zeros_like(y_true_binarized, dtype=float)
        for i, class_label in enumerate(lb.classes_):
            if class_label in label_to_idx: # label_to_idx is based on `labels`
                aligned_y_pred_proba[:, i] = y_pred_proba[:, label_to_idx[class_label]]
            # else: class_label from lb.classes_ not in y_pred_proba's original labels, so prob is 0

        # --- Plot Micro-Average ROC Curve ---
        # For micro-average, we use the binarized true labels and the aligned predicted probabilities
        fpr_micro, tpr_micro, _ = roc_curve(y_true_binarized.ravel(), aligned_y_pred_proba.ravel())
        roc_auc_micro = auc(fpr_micro, tpr_micro)

        plt.figure(figsize=(10, 8)) # New figure for ROC
        lw = 2 # line width
        plt.plot(fpr_micro, tpr_micro,
                 label=f'Micro-average ROC curve (area = {roc_auc_micro:.2f})',
                 color='deeppink', linestyle=':', linewidth=4)

        # --- Plot One-vs-Rest ROC Curve for each class ---
        # Use a suitable colormap that provides distinct colors
        colors = plt.cm.get_cmap('tab10', n_classes) if n_classes <= 10 else plt.cm.get_cmap('nipy_spectral', n_classes)


        for i in range(n_classes):
            class_label = lb.classes_[i]
            
            y_true_for_class_ovr = y_true_binarized[:, i]
            y_score_for_class = aligned_y_pred_proba[:, i]

            if np.sum(y_true_for_class_ovr == 1) == 0 or np.sum(y_true_for_class_ovr == 0) == 0:
                # print(f"Skipping OvR ROC curve for class '{class_label}' due to only one class value present in its binarized y_true.")
                continue

            fpr_class, tpr_class, _ = roc_curve(y_true_for_class_ovr, y_score_for_class)
            roc_auc_class = auc(fpr_class, tpr_class)
            plt.plot(fpr_class, tpr_class, color=colors(i), lw=lw, # Use color from colormap
                     label=f'ROC for {class_label} (area = {roc_auc_class:.2f})')

        plt.plot([0, 1], [0, 1], color='navy', lw=lw, linestyle='--', label='No Skill (area = 0.50)')
        plt.xlim([0.0, 1.0])
        plt.ylim([0.0, 1.05])
        plt.xlabel('False Positive Rate', fontsize=12)
        plt.ylabel('True Positive Rate', fontsize=12)
        plt.title('Multi-class Receiver Operating Characteristic (ROC)', fontsize=16)
        
        # Adjust legend placement
        if n_classes > 7: # Heuristic for when legend might get too crowded inside
             plt.legend(loc='center left', bbox_to_anchor=(1, 0.5), prop={'size': 8})
        else:
             plt.legend(loc="lower right", prop={'size': 9})

        plt.tight_layout(rect=[0, 0, 0.85 if n_classes > 7 else 1, 1]) # Adjust layout if legend is outside
        plt.savefig("roc_auc_multiclass_curves.png")
        print("\nROC AUC (Micro-average and OvR) curves plot saved as roc_auc_multiclass_curves.png")

    else:
        print("\nROC AUC curve plotting skipped: Not enough classes or only one class in y_true.")


    if incorrect_predictions:
        incorrect_df = pd.DataFrame(incorrect_predictions)
        incorrect_csv_path = "incorrect_nlu_predictions.csv"
        incorrect_df.to_csv(incorrect_csv_path, index=False)
        print(f"\nDetails of incorrect predictions saved to '{incorrect_csv_path}'")
    else:
        print("\nNo incorrect predictions to save.")

if __name__ == "__main__":
    asyncio.run(main())