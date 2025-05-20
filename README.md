# 🚆 A-Prototype-Chatbot-Application-for-Railway-Passenger-Support (Rasa)

A conversational AI chatbot built using [Rasa Open Source](https://rasa.com/) to assist users with Indian railway-related queries such as train schedules, ticket status, fare information, seat availability, and more. It includes fuzzy station name search, custom actions powered by Gemini API for SQL generation, and MySQL database integration.

---

## 📂 Project Structure

├── actions/
│ └── actions.py # Custom actions (SQL generation, DB queries)
├── data/
│ ├── nlu.yml # Training data for NLU
│ ├── stories.yml # Example conversations
│ └── rules.yml # Rule-based dialogues
├── domain.yml # Intents, entities, slots, responses
├── config.yml # NLU pipeline and policies
├── endpoints.yml # Action server config
├── credentials.yml # Channel connectors
├── railway_chatbot # Sample SQL for train-related tables
├── frotend/
│ ├── index.html
│ ├── style.css
│ └── script.js
├── testing (intent classification)/
│ ├── intent.py
│ ├── intent_accuracy.csv
├── testing (rouge and bert score testing)/
│ ├── rouge_bert.py
│ ├── rouge_bert.csv
