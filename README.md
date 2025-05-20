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

### 🔹 Passenger Features
- 🔍 **ask_train_status** – Get real-time status of any train
- 🧾 **ask_pnr_status** – Check PNR status for ticket confirmation
- 🚆 **find_trains** – Search for available trains between stations
- 💰 **ask_train_fare** – Check fare details for selected trains
- 🧳 **ask_booking_history** – Retrieve a user's past bookings
- ❌ **cancel_ticket** – Cancel a train ticket
- 🏢 **ask_station_info** – Get information about a station

### 🔹 Admin Features
- 📋 **admin_list_all_trains** – List all trains in the system
- 👥 **admin_list_all_users** – List all registered users
- 🔎 **admin_search_trains_by_source** – Search trains by source station

### 🔹 Other Capabilities
- 🤖 Custom actions with Gemini API for dynamic SQL generation
- 🧠 Fuzzy search using RapidFuzz for station name matching
- 🗄️ MySQL-based structured train database
- 🧩 Modular, scalable, and easy to extend

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
   
5. Install mysql connector
```bash
pip install mysql connector
```
6. Copy and run railway_chatbot database from repo in mysql workbench
   
7. For running action.py file
 ```bash
 rasa run actions
 ```

8. For running chatbot in frontend
```bash
rasa run --enable-api
rasa run --enable-api --cors "*" --debug
```

9. For testing
```bash
python rouge_bert.py 
python intent.py 
```

