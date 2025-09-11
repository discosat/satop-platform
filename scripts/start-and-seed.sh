#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

echo "--- [1/3] Seeding main authorization database... ---"
python scripts/seed_db.py

echo "--- [2/3] Starting SatOP Platform in the background... ---"
# Start the server and send it to the background (&)
python -m satop_platform -vv --install-plugin-requirements &

# Get the Process ID (PID) of the last command run in the background
APP_PID=$!

echo "--- Waiting for API to be ready at http://localhost:7889... ---"
# Use a loop to wait for the API to be available
while ! curl -s -f -o /dev/null http://localhost:7889/docs
do
  echo "API not ready yet, waiting 1 second..."
  sleep 1
done
echo "--- API is ready. ---"


echo "--- [3/3] Setting passwords for seeded users via API... ---"

# Use the insecure test token to authorize the user creation requests
ADMIN_TOKEN="test-user;satop.auth.entities.create"
API_URL="http://localhost:7889/api/plugins/login/user"

echo "  - Setting password for admin@example.com..."
curl -X 'POST' "$API_URL" \
  -H 'accept: application/json' \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{
  "email": "admin@example.com",
  "password": "adminpassword"
}'

echo ""

echo "  - Setting password for operator@example.com..."
curl -X 'POST' "$API_URL" \
  -H 'accept: application/json' \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{
  "email": "operator@example.com",
  "password": "operatorpassword"
}'

echo ""

echo "--- Seeding complete. SatOP Platform is running. ---"

# Bring the background server process to the foreground.
# The 'wait' command will pause the script here and wait for the app to exit.
# This keeps the container running and allows you to see the app's logs.
wait $APP_PID