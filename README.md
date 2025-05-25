Project was done using

Django==5.2.1
djangorestframework==3.16.0
django-cors-headers==4.2.0

Useful Commands:
python manage.py makemigrations: Initiates changes to database model
python manage.py migrate: Commits the changes to database model
python manage.py wipe_test_data:  wipes all current data stored including non super users as well as resets the id number counter
python manage.py runserver:  Starts the API

POSTMAN:

set up environment variables and Authorization on the project level
Authorization Type is API key with the key being "Authorization", the value being "Token {{auth_token}}", and it is added to header
Variables are base_url which is http://localhost:8000  and the auth_token variable
For the auth token variable make sure this script is in the login request to save the token after login:
// Extract token from response
const token = pm.response.json().token;

// Store in collection/environment variables
pm.collectionVariables.set("auth_token", token);

// Optional: Log to console for debugging
console.log("Token saved:", token);

All sub folders should by default inherit from parent

If you want to run the Run me and click folder, run the whole folder and click on the task you would like to see, or run one at a time in the folder itself.

