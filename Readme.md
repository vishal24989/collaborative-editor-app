# Collaborative Document Editor

A real-time, web-based collaborative document editor built with FastAPI, Socket.IO, and SQLite. This application allows multiple users to sign up, create documents, and edit them simultaneously using a simple and robust server-side locking mechanism. The entire application is designed to be deployed seamlessly to AWS EC2 using Docker and an automated startup script.

### ✨ Features

-   **User Authentication:** Secure user signup and login system.
-   **Document Management:** Users can create, view, and delete their own documents from a personal dashboard.
-   **Real-time Collaborative Editing:** Utilizes a "pessimistic locking" model. The first user to type gets an exclusive lock, preventing data conflicts. The lock is automatically released after a period of inactivity.
-   **Persistent Storage:** All users, documents, and content are saved in a SQLite database.
-   **Dockerized Deployment:** Fully containerized for easy, consistent, and automated deployment.

### 🛠️ Technology Stack

-   **Backend:** FastAPI
-   **Real-time Communication:** Python-SocketIO with AIOHTTP
-   **Database:** SQLite
-   **Authentication:** Passlib (for password hashing), Python-JOSE (for JWT)
-   **Containerization:** Docker
-   **Process Management:** Supervisor (within Docker)
-   **Deployment:** AWS EC2

### 📁 Project Structure

```
.
├── templates/
│   ├── dashboard.html
│   ├── editor.html
│   ├── login.html
│   └── signup.html
├── .dockerignore
├── .gitignore
├── Dockerfile
├── supervisord.conf
├── db.py
├── main.py
├── socket_server.py
├── requirements.txt
└── docs.db             # (Generated after running db.py)
```

---

## 🚀 Getting Started (Local Development)

Follow these steps to run the project on your local machine.

### Prerequisites

-   Python 3.12+
-   Git

### Setup Instructions

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/YOUR_USERNAME/collaborative-editor-app.git
    cd collaborative-editor-app
    ```

2.  **Create and activate a virtual environment:**
    ```bash
    # For macOS/Linux
    python3 -m venv .venv
    source .venv/bin/activate

    # For Windows
    python -m venv .venv
    .\.venv\Scripts\Activate.ps1
    ```

3.  **Install the required dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Initialize the database:**
    This command creates the `docs.db` file and all the necessary tables.
    ```bash
    python db.py
    ```

5.  **Run the servers:**
    You need to run the FastAPI web server and the Socket.IO server in two separate terminals.

    *   **Terminal 1 (Socket.IO Server):**
        ```bash
        python socket_server.py
        ```

    *   **Terminal 2 (FastAPI Server):**
        ```bash
        uvicorn main:app --reload
        ```

6.  **Access the application:**
    Open your browser and navigate to `http://localhost:8000`.

---

## ☁️ Automated AWS EC2 Deployment

This guide explains how to deploy the application to a free-tier AWS EC2 instance automatically using a startup script.

### Part 1: Prerequisites

1.  **An AWS Account:** You need an active AWS account.
2.  **A Public GitHub Repository:** Your project code must be in a public GitHub repository. This guide assumes you have already pushed your code.

### Part 2: The EC2 User Data Script

This script automates the entire setup process. You will paste this into the User Data field when launching your EC2 instance.

**Copy the script below and make one important change:**

```bash
#!/bin/bash
# This script runs once when the EC2 instance is first launched.

# 1. Update system packages
yum update -y

# 2. Install necessary tools: Git and Docker
yum install -y git docker

# 3. Start the Docker service and enable it to start on reboot
systemctl start docker
systemctl enable docker

# 4. Add the ec2-user to the 'docker' group to run Docker commands without sudo
usermod -a -G docker ec2-user

# 5. Run the deployment steps as the 'ec2-user'
su - ec2-user -c " \
    # !!! IMPORTANT: Replace this URL with your actual public GitHub repository URL !!!
    git clone https://github.com/YOUR_USERNAME/collaborative-editor-app.git /home/ec2-user/app; \
    
    # Navigate into the project directory
    cd /home/ec2-user/app; \
    
    # Build the Docker image from the Dockerfile
    docker build -t collaborative-editor .; \
    
    # Run the Docker container in detached mode and map the ports
    docker run -d -p 80:8000 -p 4000:4000 --restart always --name editor-app collaborative-editor; \
"
```

### Part 3: Launching the EC2 Instance

1.  Navigate to the **EC2** service in the AWS Console and click **"Launch instances"**.
2.  **Name:** Give your server a name (e.g., `automated-editor-server`).
3.  **OS Image (AMI):** Select **"Amazon Linux"** (Amazon Linux 2023 AMI is recommended).
4.  **Instance Type:** Select **`t2.micro`** (Free Tier eligible).
5.  **Key Pair:** Select or create a new key pair. You will need this to SSH into the instance for troubleshooting.
6.  **Network Settings (Security Group):** This is a critical step. Click **"Edit"** and configure the following inbound rules:

| Type       | Protocol | Port Range | Source        | Description                                  |
| :--------- | :------- | :--------- | :------------ | :------------------------------------------- |
| SSH        | TCP      | 22         | My IP         | Allows you to connect securely               |
| HTTP       | TCP      | 80         | Anywhere      | Allows web traffic to your FastAPI server    |
| Custom TCP | TCP      | 4000       | Anywhere      | Allows WebSocket traffic to your Socket.IO server |

7.  **Advanced Details:** Expand this section, scroll down to the **"User data"** field, and **paste the entire script from Part 2**.

8.  Click **"Launch instance"**.

### Part 4: Accessing and Verifying the Application

1.  **Wait for 3-5 minutes** for the instance to boot up and for the User Data script to complete.
2.  In the EC2 console, find your instance and copy its **Public IPv4 address**.
3.  Open `http://YOUR_PUBLIC_IP` in your browser. You should see the application's login page.

### Troubleshooting

If the application isn't working, SSH into your instance and check the logs:
```bash
# Connect to your instance
ssh -i "your-key.pem" ec2-user@YOUR_PUBLIC_IP

# Check the User Data script execution log for errors
cat /var/log/cloud-init-output.log

# Check if the Docker container is running
docker ps

# If it's running, check its logs for application errors
docker logs editor-app
```
