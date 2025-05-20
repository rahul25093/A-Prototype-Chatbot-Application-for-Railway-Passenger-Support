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



---

## 🚀 Features

- 🔍 Train search and schedule
- 💺 Seat availability and train types
- 💸 Fare inquiry
- 🧾 PNR status check
- 🍱 Food and 📶 Wi-Fi availability
- 🙋 Complaint registration and refund policies
- 🤖 Custom action server using Gemini API for dynamic SQL generation
- 🧠 Fuzzy search for station names

---

## 🛠️ Installation & Setup

### 1. Clone the repository

```bash
git clone https://github.com/rahul25093/A-Prototype-Chatbot-Application-for-Railway-Passenger-Support.git
cd A-Prototype-Chatbot-Application-for-Railway-Passenger-Support

```
2. Create and activate a virtual environment

```bash
python -m venv rasa_env
.\rasa_env\Scripts\Activate
```

3. Install dependencies

```bash
pip intall rasa
rasa train
rasa shell
```

4. Enable my sql connector in enpoints.yml
5
. Install mysql connector
```bash
pip install mysql connector
```

6. For running chatbot in frontend
```bash
rasa run --enable-api
rasa run --enable-api --cors "*" --debug
```

7. For testing
```bash
python rouge_bert.py 
python intent.py 
```

