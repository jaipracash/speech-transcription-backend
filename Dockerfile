FROM python:3.10

# Install system dependencies as root
USER root
RUN apt-get update && apt-get install -y wget unzip && rm -rf /var/lib/apt/lists/*

# Create a non-root user (Hugging Face Requirement)
RUN useradd -m -u 1000 user
USER user
ENV PATH="/home/user/.local/bin:$PATH"

WORKDIR /app

# Copy requirements and install
COPY --chown=user ./requirements.txt requirements.txt
RUN pip install --no-cache-dir --upgrade -r requirements.txt

# Copy the rest of the app files
COPY --chown=user . /app

# Hugging Face Spaces port
EXPOSE 7860

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]
