FROM python

WORKDIR /app
COPY requirements.txt /app/requirements.txt

RUN pip install -r requirements.txt --no-cache-dir

RUN mkdir cache
RUN touch cache/auth.json
