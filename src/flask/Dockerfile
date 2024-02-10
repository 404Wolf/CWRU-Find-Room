FROM python:3.12

# Set the working directory
WORKDIR /app

COPY requirements.txt requirements.txt

# Install dependencies
RUN pip install -r requirements.txt --no-cache-dir

RUN mkdir cache
RUN echo '{}' > 'cache/rooms.json'
