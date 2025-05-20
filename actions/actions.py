# actions.py

from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, UserUtteranceReverted
import mysql.connector
import traceback # For detailed error logging
import datetime

# --- Database Connection Configuration ---
# !!! IMPORTANT: Replace with your actual database credentials !!!
DB_CONFIG = {
    "host": "localhost",
    "user": "root",          # Replace with your MySQL username
    "password": "Rp@25093",  # Replace with your MySQL password
    "database": "railway_chatbot" # Replace with your database name
}

def connect_db():
    """Establishes a connection to the MySQL database."""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        # Setting autocommit might be useful for simple actions, but manage transactions explicitly if needed
        # conn.autocommit = True # Uncomment if you prefer autocommit for simple operations
        return conn
    except mysql.connector.Error as err:
        print(f"ERROR connecting to MySQL: {err}")
        traceback.print_exc() # Print full traceback for connection errors
        return None

# --- Helper Function for Closing DB Resources ---
def close_db_resources(cursor=None, conn=None):
    """Safely closes cursor and connection."""
    if cursor:
        try:
            cursor.close()
        except Exception as e:
            print(f"Warning: Error closing cursor: {e}")
    if conn and conn.is_connected():
        try:
            conn.close()
        except Exception as e:
            print(f"Warning: Error closing connection: {e}")

# --- Action Classes ---

# actions.py
# ... (DB_CONFIG, connect_db, close_db_resources remain the same) ...

class ActionGetTrainStatus(Action):
    def name(self) -> Text:
        return "action_get_train_status"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        train_number = tracker.get_slot("train_number")
        conn = None
        cursor = None

        if not train_number:
            dispatcher.utter_message(text="Please provide a train number.")
            return [SlotSet("train_number", None)]

        conn = connect_db()
        if not conn:
            dispatcher.utter_message(text="Sorry, I'm having trouble connecting to the railway database right now.")
            return [SlotSet("train_number", None)]

        try:
            cursor = conn.cursor(dictionary=True)
            # Fetch the raw 'timings' column
            query = """
                SELECT train_number, from_location, to_location,
                       timings, status  # <-- Fetch raw timings
                FROM train_details
                WHERE train_number = %s
            """
            cursor.execute(query, (train_number,))
            train = cursor.fetchone()

            if train:
                raw_timings_value = train.get('timings')
                print(f"DEBUG in action_get_train_status: train_number='{train_number}' -> "
                      f"RAW train['timings'] = {raw_timings_value}, "
                      f"type = {type(raw_timings_value)}")

                departure_display = "N/A"
                if raw_timings_value is not None:
                    # Try to format it in Python.
                    # mysql.connector can return datetime.timedelta for TIME columns
                    if isinstance(raw_timings_value, str):
                        # If it's a string like "22:10:45", parse and format
                        try:
                            # Simplistic parsing, assumes HH:MM:SS or HH:MM
                            parts = raw_timings_value.split(':')
                            if len(parts) >= 2:
                                departure_display = f"{parts[0].zfill(2)}:{parts[1].zfill(2)}"
                        except Exception as time_parse_err:
                            print(f"ERROR parsing time string '{raw_timings_value}': {time_parse_err}")
                            departure_display = "Error: Invalid time"
                    elif hasattr(raw_timings_value, 'hours') and hasattr(raw_timings_value, 'minutes'):
                        # Handles datetime.timedelta (common for TIME type from mysql.connector)
                        # or other time-like objects with these attributes
                        try:
                            # Ensure hours and minutes are integers before formatting
                            hours = int(raw_timings_value.hours)
                            minutes = int(raw_timings_value.minutes)
                            departure_display = f"{hours:02d}:{minutes:02d}"
                        except (TypeError, ValueError) as time_conv_err:
                             print(f"ERROR converting time object components for '{raw_timings_value}': {time_conv_err}")
                             departure_display = "Error: Invalid time obj"
                    else:
                        # Fallback if it's an unknown type but not None
                        departure_display = str(raw_timings_value)


                msg = (
                    f"Train {train.get('train_number', 'N/A')} "
                    f"({train.get('from_location', 'N/A')} to {train.get('to_location', 'N/A')}):\n"
                    f"- Scheduled Departure: {departure_display}\n"
                    f"- Current Status: {train.get('status', 'N/A')}"
                )
            else:
                msg = f"Sorry, I couldn't find any details for train number {train_number}."
            
            dispatcher.utter_message(text=msg)

        except mysql.connector.Error as err:
            print(f"ERROR [DB] in {self.name()} for train {train_number}: {err}")
            traceback.print_exc()
            dispatcher.utter_message(text="Sorry, a database error occurred while fetching train status.")
        except Exception as e:
            print(f"ERROR [Unexpected] in {self.name()} for train {train_number}: {e}")
            traceback.print_exc()
            dispatcher.utter_message(text="An unexpected error occurred while fetching train status.")
        finally:
            close_db_resources(cursor, conn)

        return [SlotSet("train_number", None)]
        
# actions.py
# ... (DB_CONFIG, connect_db, close_db_resources remain the same) ...

import datetime # Add this import for date/time formatting

class ActionPnrStatus(Action):
    def name(self) -> Text:
        return "action_pnr_status"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        pnr_number_str = tracker.get_slot("pnr_number")
        conn = None
        cursor = None

        if not pnr_number_str:
            dispatcher.utter_message(text="Please provide your PNR number.")
            return [SlotSet("pnr_number", None)]

        try:
            if not pnr_number_str.isdigit() or len(pnr_number_str) != 10:
                 raise ValueError("PNR must be a 10-digit number.")
            pnr_number = int(pnr_number_str)
        except ValueError as ve:
            dispatcher.utter_message(text=f"That doesn't look like a valid PNR number. {ve}")
            return [SlotSet("pnr_number", None)]

        conn = connect_db()
        if not conn:
            dispatcher.utter_message(text="Sorry, I'm having trouble connecting to the railway database right now.")
            return [SlotSet("pnr_number", None)]

        try:
            cursor = conn.cursor(dictionary=True)
            # Fetch raw journey_date from ps and raw timings from td
            query = """
                SELECT ps.pnr_number, ps.seat_number,
                       ps.journey_date,  -- Fetch raw journey_date
                       ps.status AS pnr_ticket_status,
                       td.train_number, td.from_location, td.to_location,
                       td.timings as train_timings,      -- Fetch raw train timings
                       td.status AS train_operational_status
                FROM pnr_status ps
                JOIN train_details td ON ps.train_number = td.train_number
                WHERE ps.pnr_number = %s
            """
            cursor.execute(query, (pnr_number,))
            pnr_details = cursor.fetchone()

            if pnr_details:
                raw_journey_date = pnr_details.get('journey_date')
                raw_train_timings = pnr_details.get('train_timings')

                print(f"DEBUG in action_pnr_status: pnr='{pnr_number}'")
                print(f"  -> RAW ps.journey_date from DB = {raw_journey_date}, type = {type(raw_journey_date)}")
                print(f"  -> RAW td.timings from DB = {raw_train_timings}, type = {type(raw_train_timings)}")

                journey_date_display = "N/A"
                if raw_journey_date:
                    if isinstance(raw_journey_date, datetime.date):
                        try:
                            journey_date_display = raw_journey_date.strftime('%d-%b-%Y') # e.g., 15-Aug-2024
                        except Exception as fmt_err:
                            print(f"ERROR formatting journey_date object: {fmt_err}")
                            journey_date_display = str(raw_journey_date) # fallback
                    elif isinstance(raw_journey_date, str): # If it comes as a string "YYYY-MM-DD"
                        try:
                            dt_obj = datetime.datetime.strptime(raw_journey_date, '%Y-%m-%d').date()
                            journey_date_display = dt_obj.strftime('%d-%b-%Y')
                        except ValueError:
                            journey_date_display = raw_journey_date # fallback if parse fails
                    else:
                        journey_date_display = str(raw_journey_date)


                departure_time_display = "N/A"
                if raw_train_timings:
                    if isinstance(raw_train_timings, (datetime.time, datetime.timedelta)): # timedelta is common for TIME
                        try:
                            # For timedelta, access hours and minutes
                            if hasattr(raw_train_timings, 'seconds'): # timedelta
                                hours = raw_train_timings.seconds // 3600
                                minutes = (raw_train_timings.seconds // 60) % 60
                                departure_time_display = f"{hours:02d}:{minutes:02d}"
                            elif hasattr(raw_train_timings, 'hour'): # datetime.time
                                departure_time_display = raw_train_timings.strftime('%H:%M')
                        except Exception as fmt_err:
                            print(f"ERROR formatting train_timings object: {fmt_err}")
                            departure_time_display = str(raw_train_timings) # fallback
                    elif isinstance(raw_train_timings, str): # If it's "HH:MM:SS" string
                        try:
                            parts = raw_train_timings.split(':')
                            if len(parts) >= 2:
                                departure_time_display = f"{parts[0].zfill(2)}:{parts[1].zfill(2)}"
                        except Exception as parse_err:
                             print(f"ERROR parsing train_timings string: {parse_err}")
                             departure_time_display = raw_train_timings
                    else:
                        departure_time_display = str(raw_train_timings)

                msg = (
                    f"PNR Status for {pnr_details.get('pnr_number', 'N/A')}:\n"
                    f"- Journey Date: {journey_date_display}\n"
                    f"- Train: {pnr_details.get('train_number', 'N/A')} ({pnr_details.get('from_location', 'N/A')} to {pnr_details.get('to_location', 'N/A')})\n"
                    f"- Departure Time: {departure_time_display}\n"
                    f"- Seat: {pnr_details.get('seat_number', 'N/A')}\n"
                    f"- Ticket Status: {pnr_details.get('pnr_ticket_status', 'N/A')}\n"
                    f"- Train Operational Status: {pnr_details.get('train_operational_status', 'N/A')}"
                )
            else:
                msg = f"Sorry, I couldn't find any details for PNR number {pnr_number}."
            dispatcher.utter_message(text=msg)

        except mysql.connector.Error as err:
            print(f"ERROR [DB] in {self.name()} for PNR {pnr_number}: {err}")
            traceback.print_exc()
            dispatcher.utter_message(text="Sorry, a database error occurred while fetching PNR status.")
        except Exception as e:
            print(f"ERROR [Unexpected] in {self.name()} for PNR {pnr_number}: {e}")
            traceback.print_exc()
            dispatcher.utter_message(text="An unexpected error occurred while fetching PNR status.")
        finally:
            close_db_resources(cursor, conn)

        return [SlotSet("pnr_number", None)]

# actions.py
# ... (DB_CONFIG, connect_db, close_db_resources, other imports like datetime remain the same) ...

class ActionFindTrains(Action):
    def name(self) -> Text:
        return "action_find_trains"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        from_location = tracker.get_slot("from_location")
        to_location = tracker.get_slot("to_location")
        conn = None
        cursor = None

        if not from_location:
            # In your actions.py, you used dispatcher.utter_message(response="utter_ask_from_location")
            # This is good practice. Keeping it consistent.
            dispatcher.utter_message(response="utter_ask_from_location")
            return [SlotSet("from_location", None), SlotSet("to_location", None)]

        if not to_location:
            dispatcher.utter_message(response="utter_ask_to_location")
            return [SlotSet("from_location", None), SlotSet("to_location", None)] # Clear both if one is missing after prompt

        conn = connect_db()
        if not conn:
            dispatcher.utter_message(text="Sorry, I'm having trouble connecting to the railway database right now.")
            return [SlotSet("from_location", None), SlotSet("to_location", None)]

        try:
            cursor = conn.cursor(dictionary=True)
            # Fetch raw 'timings' column
            query = """
                SELECT train_number, from_location, to_location,
                       timings, status  -- Fetch raw timings
                FROM train_details
                WHERE LOWER(from_location) LIKE %s AND LOWER(to_location) LIKE %s
                ORDER BY timings
            """
            param_from = f"%{from_location.lower()}%"
            param_to = f"%{to_location.lower()}%"

            cursor.execute(query, (param_from, param_to))
            trains_data = cursor.fetchall() # Renamed to avoid conflict with train loop variable

            if trains_data:
                messages = [f"Trains from {from_location.title()} to {to_location.title()}:"]
                limit = 10
                for i, train_row in enumerate(trains_data): # Use train_row for clarity
                    if i >= limit:
                        messages.append(f"\n(Showing first {limit} of {len(trains_data)} trains found...)")
                        break
                    
                    raw_timings_value = train_row.get('timings')
                    # --- DEBUG PRINT for this specific action ---
                    print(f"DEBUG in action_find_trains: train='{train_row.get('train_number')}' -> "
                          f"RAW timings = {raw_timings_value}, type = {type(raw_timings_value)}")
                    # --- END DEBUG PRINT ---

                    departure_time_display = "N/A"
                    if raw_timings_value:
                        if isinstance(raw_timings_value, (datetime.time, datetime.timedelta)):
                            try:
                                if hasattr(raw_timings_value, 'seconds'): # timedelta
                                    hours = raw_timings_value.seconds // 3600
                                    minutes = (raw_timings_value.seconds // 60) % 60
                                    departure_time_display = f"{hours:02d}:{minutes:02d}"
                                elif hasattr(raw_timings_value, 'hour'): # datetime.time
                                    departure_time_display = raw_timings_value.strftime('%H:%M')
                            except Exception as fmt_err:
                                print(f"ERROR formatting timings object for train '{train_row.get('train_number')}': {fmt_err}")
                                departure_time_display = str(raw_timings_value)
                        elif isinstance(raw_timings_value, str):
                            try:
                                parts = raw_timings_value.split(':')
                                if len(parts) >= 2:
                                    departure_time_display = f"{parts[0].zfill(2)}:{parts[1].zfill(2)}"
                            except Exception as parse_err:
                                print(f"ERROR parsing timings string for train '{train_row.get('train_number')}': {parse_err}")
                                departure_time_display = raw_timings_value
                        else:
                            departure_time_display = str(raw_timings_value)

                    part = (
                        f"- Train {train_row.get('train_number', 'N/A')}: Departs at {departure_time_display}, Status: {train_row.get('status', 'N/A')}"
                    )
                    messages.append(part)
                dispatcher.utter_message(text="\n".join(messages))
            else:
                dispatcher.utter_message(text=f"Sorry, I couldn't find any direct trains matching '{from_location.title()}' to '{to_location.title()}'.")

        except mysql.connector.Error as err:
            print(f"ERROR [DB] in {self.name()}: {err}")
            traceback.print_exc()
            dispatcher.utter_message(text="Sorry, a database error occurred while searching for trains.")
        except Exception as e:
            print(f"ERROR [Unexpected] in {self.name()}: {e}")
            traceback.print_exc()
            dispatcher.utter_message(text="An unexpected error occurred while searching for trains.")
        finally:
            close_db_resources(cursor, conn)

        return [SlotSet("from_location", None), SlotSet("to_location", None)]


class ActionTrainFare(Action):
    def name(self) -> Text:
        return "action_train_fare"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        train_number = tracker.get_slot("train_number")
        travel_class = tracker.get_slot("travel_class")
        conn = None
        cursor = None

        # Allow context from find_trains if needed, but prioritize explicit requests
        # Example: Could check tracker.latest_action_name == "action_find_trains"

        if not train_number:
            dispatcher.utter_message(response="utter_ask_train_number") # Use domain utterance
            return [SlotSet("train_number", None), SlotSet("travel_class", None)]

        if not travel_class:
             # Provide train number context if available
            prompt = f"Which class are you interested in for train {train_number}? (e.g., Sleeper, 3A, 2A, CC)" if train_number else "Which class are you interested in? (e.g., Sleeper, 3A, 2A, CC)"
            dispatcher.utter_message(text=prompt)
            # Keep train_number slot if it was already filled
            return [SlotSet("travel_class", None)]


        conn = connect_db()
        if not conn:
            dispatcher.utter_message(text="Sorry, I'm having trouble connecting to the railway database right now.")
            return [SlotSet("train_number", None), SlotSet("travel_class", None)]

        try:
            cursor = conn.cursor(dictionary=True)
            # Assuming train_fare table stores fare for specific train and class
            # JOIN on train_details might not be needed if fare table has all info,
            # but kept here for potential route validation if schema requires it.
            query = """
                SELECT tf.class, tf.fare
                FROM train_fare tf
                WHERE tf.train_number = %s AND LOWER(tf.class) LIKE %s
            """
            # Prepare parameter for class search (case-insensitive)
            class_search_term = f"%{travel_class.lower()}%"

            cursor.execute(query, (train_number, class_search_term))
            fares = cursor.fetchall()

            if fares:
                messages = [f"Fares for train {train_number}:"]
                matched_classes = set()
                for fare_info in fares:
                    # Format fare, assuming it's a numeric type in DB
                    formatted_fare = f"₹{fare_info['fare']:.2f}" if isinstance(fare_info['fare'], (int, float)) else str(fare_info['fare'])
                    messages.append(f"- {fare_info['class']}: {formatted_fare}")
                    matched_classes.add(fare_info['class'].lower())

                # Add note if LIKE matched multiple classes unintentionally
                if len(fares) > 1 and travel_class.lower() not in matched_classes:
                     messages.append(f"\n(Note: '{travel_class}' matched multiple classes. Please be more specific if needed.)")
                dispatcher.utter_message(text="\n".join(messages))
            else:
                # Check if the train exists at all to give a better message
                cursor.execute("SELECT 1 FROM train_details WHERE train_number = %s", (train_number,))
                train_exists = cursor.fetchone()
                if train_exists:
                    dispatcher.utter_message(text=f"Sorry, I couldn't find {travel_class.title()} class fare information for train {train_number}. It might not exist or the class name is different.")
                else:
                    dispatcher.utter_message(text=f"Sorry, I couldn't find train {train_number} to check fares.")

        except mysql.connector.Error as err:
            print(f"ERROR [DB] in {self.name()}: {err}")
            traceback.print_exc()
            dispatcher.utter_message(text="Sorry, a database error occurred while fetching train fares.")
        except Exception as e:
            print(f"ERROR [Unexpected] in {self.name()}: {e}")
            traceback.print_exc()
            dispatcher.utter_message(text="An unexpected error occurred while fetching train fares.")
        finally:
            close_db_resources(cursor, conn)

        return [SlotSet("train_number", None), SlotSet("travel_class", None)]


class ActionBookingHistory(Action):
    def name(self) -> Text:
        return "action_booking_history"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        user_id_str = tracker.get_slot("user_id")
        conn = None
        cursor = None

        if not user_id_str:
            dispatcher.utter_message(response="utter_ask_user_id")
            return [SlotSet("user_id", None)]

        try:
            if not user_id_str.isdigit():
                 raise ValueError("User ID must be a number.")
            user_id = int(user_id_str)
        except ValueError as ve:
            dispatcher.utter_message(text=f"Invalid User ID provided. {ve}")
            return [SlotSet("user_id", None)]

        conn = connect_db()
        if not conn:
            dispatcher.utter_message(text="Sorry, I'm having trouble connecting to the database right now.")
            return [SlotSet("user_id", None)]

        try:
            cursor = conn.cursor(dictionary=True)
            # 1. Get user's name
            cursor.execute("SELECT name FROM user_details WHERE user_id = %s", (user_id,))
            user = cursor.fetchone()
            if not user:
                dispatcher.utter_message(text=f"Sorry, I couldn't find a user with ID {user_id}.")
                close_db_resources(cursor, conn)
                return [SlotSet("user_id", None)]
            user_name = user['name']

            # 2. Get booking history - Fetch RAW dates
            query = """
                SELECT bh.pnr_number,
                       bh.booking_date,      -- Fetch raw booking_date
                       ps.journey_date,      -- Fetch raw journey_date
                       ps.seat_number, ps.status AS pnr_ticket_status,
                       td.train_number, td.from_location, td.to_location
                       -- td.timings is not used in the original message, so not fetching here
                       -- td.status AS train_operational_status -- also not used in original message
                FROM booking_history bh
                JOIN pnr_status ps ON bh.pnr_number = ps.pnr_number
                JOIN train_details td ON ps.train_number = td.train_number
                WHERE bh.user_id = %s
                ORDER BY ps.journey_date DESC, bh.booking_date DESC
            """
            cursor.execute(query, (user_id,))
            bookings_data = cursor.fetchall() # Renamed to avoid conflict

            if bookings_data:
                messages = [f"Booking history for {user_name} (User ID: {user_id}):"]
                limit = 5
                for i, booking_row in enumerate(bookings_data): # Use booking_row for clarity
                    if i >= limit:
                        messages.append(f"\n(Showing latest {limit} of {len(bookings_data)} bookings...)")
                        break
                    
                    raw_booking_date = booking_row.get('booking_date')
                    raw_journey_date = booking_row.get('journey_date')

                    # --- DEBUG PRINTS for this specific action ---
                    print(f"DEBUG in action_booking_history: PNR='{booking_row.get('pnr_number')}'")
                    print(f"  -> RAW booking_date = {raw_booking_date}, type = {type(raw_booking_date)}")
                    print(f"  -> RAW journey_date = {raw_journey_date}, type = {type(raw_journey_date)}")
                    # --- END DEBUG PRINTS ---

                    booking_date_display = "N/A"
                    if raw_booking_date:
                        if isinstance(raw_booking_date, datetime.date):
                            try:
                                booking_date_display = raw_booking_date.strftime('%d-%b-%Y')
                            except Exception as fmt_err:
                                print(f"ERROR formatting booking_date object: {fmt_err}")
                                booking_date_display = str(raw_booking_date)
                        elif isinstance(raw_booking_date, str):
                            try:
                                dt_obj = datetime.datetime.strptime(raw_booking_date, '%Y-%m-%d').date()
                                booking_date_display = dt_obj.strftime('%d-%b-%Y')
                            except ValueError: booking_date_display = raw_booking_date
                        else: booking_date_display = str(raw_booking_date)

                    journey_date_display = "N/A"
                    if raw_journey_date:
                        if isinstance(raw_journey_date, datetime.date):
                            try:
                                journey_date_display = raw_journey_date.strftime('%d-%b-%Y')
                            except Exception as fmt_err:
                                print(f"ERROR formatting journey_date object: {fmt_err}")
                                journey_date_display = str(raw_journey_date)
                        elif isinstance(raw_journey_date, str):
                            try:
                                dt_obj = datetime.datetime.strptime(raw_journey_date, '%Y-%m-%d').date()
                                journey_date_display = dt_obj.strftime('%d-%b-%Y')
                            except ValueError: journey_date_display = raw_journey_date
                        else: journey_date_display = str(raw_journey_date)

                    messages.append(
                        f"- PNR: {booking_row.get('pnr_number', 'N/A')} (Booked: {booking_date_display}, Journey: {journey_date_display})\n"
                        f"  Train: {booking_row.get('train_number', 'N/A')} ({booking_row.get('from_location', 'N/A')} to {booking_row.get('to_location', 'N/A')})\n"
                        f"  Seat: {booking_row.get('seat_number', 'N/A')}, Status: {booking_row.get('pnr_ticket_status', 'N/A')}"
                    )
                dispatcher.utter_message(text="\n".join(messages))
            else:
                dispatcher.utter_message(text=f"No booking history found for User ID {user_id} ({user_name}).")

        except mysql.connector.Error as err:
            print(f"ERROR [DB] in {self.name()} for user {user_id}: {err}")
            traceback.print_exc()
            dispatcher.utter_message(text="Sorry, a database error occurred while fetching booking history.")
        except Exception as e:
            print(f"ERROR [Unexpected] in {self.name()} for user {user_id}: {e}")
            traceback.print_exc()
            dispatcher.utter_message(text="An unexpected error occurred while fetching booking history.")
        finally:
            close_db_resources(cursor, conn)

        return [SlotSet("user_id", None)]

# ... (Other action classes) ...

class ActionCancelTicket(Action):
    def name(self) -> Text:
        return "action_cancel_ticket"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        pnr_number_str = tracker.get_slot("pnr_number_to_cancel")
        conn = None
        cursor = None

        if not pnr_number_str:
            dispatcher.utter_message(response="utter_ask_pnr_to_cancel") # Use domain utterance
            return [SlotSet("pnr_number_to_cancel", None)]

        try:
            # Basic validation
             if not pnr_number_str.isdigit() or len(pnr_number_str) != 10:
                 raise ValueError("PNR must be a 10-digit number.")
             pnr_number = int(pnr_number_str)
        except ValueError as ve:
            dispatcher.utter_message(text=f"That PNR number doesn't seem valid. {ve}")
            return [SlotSet("pnr_number_to_cancel", None)]

        conn = connect_db()
        if not conn:
            dispatcher.utter_message(text="Sorry, I'm having trouble connecting to the database right now.")
            return [SlotSet("pnr_number_to_cancel", None)]

        try:
            cursor = conn.cursor(dictionary=True)
            conn.start_transaction() # Start transaction for update

            # Check current status
            cursor.execute("SELECT status FROM pnr_status WHERE pnr_number = %s FOR UPDATE", (pnr_number,)) # Lock row
            pnr_info = cursor.fetchone()

            if not pnr_info:
                dispatcher.utter_message(text=f"Sorry, PNR number {pnr_number} was not found.")
                conn.rollback() # Rollback transaction
                return [SlotSet("pnr_number_to_cancel", None)]

            current_status = pnr_info["status"].lower()
            if current_status == "cancelled":
                dispatcher.utter_message(text=f"PNR {pnr_number} is already cancelled.")
                conn.rollback() # Rollback transaction
                return [SlotSet("pnr_number_to_cancel", None)]
            # Add checks for other non-cancellable statuses if needed (e.g., 'journey complete')
            # elif current_status == "journey complete":
            #     dispatcher.utter_message(text=f"Cannot cancel PNR {pnr_number} as the journey is complete.")
            #     conn.rollback()
            #     return [SlotSet("pnr_number_to_cancel", None)]

            # Perform update
            update_query = "UPDATE pnr_status SET status = 'Cancelled' WHERE pnr_number = %s"
            cursor.execute(update_query, (pnr_number,))

            if cursor.rowcount > 0:
                conn.commit() # Commit transaction
                # Optionally: Log cancellation action here
                msg = f"PNR number {pnr_number} has been successfully cancelled."
            else:
                # Should not happen if FOR UPDATE worked, but as a safeguard
                conn.rollback() # Rollback transaction
                msg = f"Could not cancel PNR {pnr_number}. An unexpected issue occurred (possibly already cancelled by another process)."
            dispatcher.utter_message(text=msg)

        except mysql.connector.Error as err:
            print(f"ERROR [DB] in {self.name()}: {err}")
            traceback.print_exc()
            if conn: conn.rollback() # Rollback on error
            dispatcher.utter_message(text="Sorry, a database error occurred while trying to cancel the ticket.")
        except Exception as e:
            print(f"ERROR [Unexpected] in {self.name()}: {e}")
            traceback.print_exc()
            if conn: conn.rollback() # Rollback on error
            dispatcher.utter_message(text="An unexpected error occurred during cancellation.")
        finally:
            close_db_resources(cursor, conn)

        return [SlotSet("pnr_number_to_cancel", None)]


class ActionAskStationInfo(Action):
    def name(self) -> Text:
        # Ensure this EXACT name is in domain.yml -> actions:
        return "action_ask_station_info"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        station_identifier = tracker.get_slot("station_identifier")
        conn = None
        cursor = None

        if not station_identifier:
            dispatcher.utter_message(response="utter_ask_station_identifier") # Use domain utterance
            return [SlotSet("station_identifier", None)]

        conn = connect_db()
        if not conn:
            dispatcher.utter_message(text="Sorry, I'm having trouble connecting to the database right now.")
            return [SlotSet("station_identifier", None)]

        try:
            cursor = conn.cursor(dictionary=True)
            # Query a hypothetical 'stations' table by name or code
            # Assumes columns: station_code, station_name, details, state
            query = """
                SELECT station_code, station_name, details, state
                FROM stations
                WHERE LOWER(station_name) LIKE %s OR LOWER(station_code) = LOWER(%s)
            """
            # Prepare parameters for LIKE and exact match
            name_param = f"%{station_identifier.lower()}%"
            code_param = station_identifier.lower()

            cursor.execute(query, (name_param, code_param))
            station_info = cursor.fetchone() # Assuming name/code is unique enough to fetch one

            if station_info:
                details = station_info.get('details') or "No specific details available."
                state = f" ({station_info.get('state')})" if station_info.get('state') else ""
                msg = (
                    f"Station: {station_info['station_name']} ({station_info['station_code']}){state}\n"
                    f"- Details: {details}"
                )
                dispatcher.utter_message(text=msg)
            else:
                dispatcher.utter_message(text=f"Sorry, I couldn't find information for station '{station_identifier}'. Please check the name or code.")

        except mysql.connector.Error as err:
            print(f"ERROR [DB] in {self.name()}: {err}")
            traceback.print_exc()
            dispatcher.utter_message(text="Sorry, a database error occurred while fetching station information.")
        except Exception as e:
            print(f"ERROR [Unexpected] in {self.name()}: {e}")
            traceback.print_exc()
            dispatcher.utter_message(text="An unexpected error occurred while fetching station information.")
        finally:
            close_db_resources(cursor, conn)

        return [SlotSet("station_identifier", None)]

# --- Admin/Listing Actions ---

class ActionListAllTrains(Action):
    def name(self) -> Text:
        return "action_list_all_trains"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        conn = None
        cursor = None
        conn = connect_db()
        if not conn:
            dispatcher.utter_message(text="Sorry, I'm having trouble connecting to the database right now.")
            return []

        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT train_number, from_location, to_location, TIME_FORMAT(timings, '%%H:%%i') as departure_time, status FROM train_details ORDER BY train_number")
            results = cursor.fetchall()

            if results:
                messages = ["Available Trains (showing a sample):"]
                limit = 15
                for i, row in enumerate(results):
                     if i >= limit:
                        messages.append(f"\n(Showing first {limit} of {len(results)} trains...)")
                        break
                     messages.append(f"- Train {row['train_number']}: {row['from_location']} → {row['to_location']} @ {row['departure_time']}, Status: {row['status']}")
                dispatcher.utter_message(text="\n".join(messages))
            else:
                dispatcher.utter_message(text="No trains found in the database.")
        except mysql.connector.Error as err:
            print(f"ERROR [DB] in {self.name()}: {err}")
            traceback.print_exc()
            dispatcher.utter_message(text="An error occurred while listing trains.")
        except Exception as e:
            print(f"ERROR [Unexpected] in {self.name()}: {e}")
            traceback.print_exc()
            dispatcher.utter_message(text="An unexpected error occurred while listing trains.")
        finally:
            close_db_resources(cursor, conn)
        return []

class ActionListAllUserDetails(Action):
    def name(self) -> Text:
        return "action_list_all_user_details"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        # !! SECURITY WARNING !! Highly sensitive action. Restrict access severely in production.
        print("WARNING: Executing sensitive action 'action_list_all_user_details'")

        conn = None
        cursor = None
        conn = connect_db()
        if not conn:
            dispatcher.utter_message(text="Sorry, I'm having trouble connecting to the database right now.")
            return []

        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT user_id, name, email_id, phone_number FROM user_details ORDER BY user_id")
            results = cursor.fetchall()

            if results:
                messages = ["User Details (Admin View - Limited Sample):"]
                limit = 10
                for i, row in enumerate(results):
                    if i >= limit:
                        messages.append(f"\n(Showing first {limit} of {len(results)} users...)")
                        break
                    # Basic masking for demo - consider more robust masking/logging
                    email_parts = row['email_id'].split('@') if row['email_id'] else ['','']
                    masked_email = f"{email_parts[0][:2]}...@{'...' if len(email_parts)<2 else email_parts[1]}"
                    phone = row['phone_number'] or ''
                    masked_phone = f"...{phone[-4:]}" if len(phone) > 4 else phone
                    messages.append(f"- ID: {row['user_id']}, Name: {row['name']}, Email: {masked_email}, Phone: {masked_phone}")
                messages.append("\nNote: Displaying user details is a security risk.")
                dispatcher.utter_message(text="\n".join(messages))
            else:
                dispatcher.utter_message(text="No user details found.")
        except mysql.connector.Error as err:
            print(f"ERROR [DB] in {self.name()}: {err}")
            traceback.print_exc()
            dispatcher.utter_message(text="An error occurred while listing user details.")
        except Exception as e:
            print(f"ERROR [Unexpected] in {self.name()}: {e}")
            traceback.print_exc()
            dispatcher.utter_message(text="An unexpected error occurred while listing user details.")
        finally:
            close_db_resources(cursor, conn)
        return []

class ActionSearchTrainsBySource(Action):
    def name(self) -> Text:
        return "action_search_trains_by_source"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        source = tracker.get_slot("from_location")
        conn = None
        cursor = None

        if not source:
            dispatcher.utter_message(text="Please specify the source station to search from.")
            return [SlotSet("from_location", None)]

        conn = connect_db()
        if not conn:
            dispatcher.utter_message(text="Sorry, I'm having trouble connecting to the database right now.")
            return [SlotSet("from_location", None)]

        try:
            cursor = conn.cursor(dictionary=True)
            query = """
                SELECT train_number, from_location, to_location,
                       TIME_FORMAT(timings, '%%H:%%i') as departure_time, status
                FROM train_details
                WHERE LOWER(from_location) LIKE %s
                ORDER BY timings
            """
            search_term = f"%{source.lower()}%"
            cursor.execute(query, (search_term,))
            results = cursor.fetchall()

            if results:
                messages = [f"Trains departing from stations like '{source.title()}':"]
                limit = 15
                for i, row in enumerate(results):
                    if i >= limit:
                        messages.append(f"\n(Showing first {limit} of {len(results)} trains...)")
                        break
                    messages.append(f"- Train {row['train_number']}: From {row['from_location']} to {row['to_location']} @ {row['departure_time']}, Status: {row['status']}")
                dispatcher.utter_message(text="\n".join(messages))
            else:
                dispatcher.utter_message(text=f"No trains found departing from stations matching '{source.title()}'.")
        except mysql.connector.Error as err:
            print(f"ERROR [DB] in {self.name()}: {err}")
            traceback.print_exc()
            dispatcher.utter_message(text="An error occurred while searching trains by source.")
        except Exception as e:
            print(f"ERROR [Unexpected] in {self.name()}: {e}")
            traceback.print_exc()
            dispatcher.utter_message(text="An unexpected error occurred while searching trains by source.")
        finally:
            close_db_resources(cursor, conn)
        return [SlotSet("from_location", None)]


# --- Fallback Action ---
class ActionDefaultFallback(Action):
    def name(self) -> Text:
        return "action_default_fallback"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        # Use one of the default utterances from domain.yml
        dispatcher.utter_message(response="utter_default")
        # Optionally revert the last user utterance if fallback shouldn't influence dialogue state
        # return [UserUtteranceReverted()]
        return []