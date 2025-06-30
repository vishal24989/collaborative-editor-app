# Step 1: Use an official Python runtime as a parent image
FROM python:3.12-slim

# Step 2: Set the working directory in the container
WORKDIR /app

# Step 3: Copy the requirements file into the container
COPY requirements.txt .

# Step 4: Install Supervisor and the Python dependencies
RUN apt-get update && apt-get install -y supervisor && \
    pip install --no-cache-dir -r requirements.txt

# Step 5: Copy the rest of your application code into the container
COPY . .

# Step 6: Copy the supervisor configuration file
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Step 7: Expose the ports the container will listen on
EXPOSE 8000
EXPOSE 4000

# Step 8: Command to run supervisor
CMD ["/usr/bin/supervisord"]