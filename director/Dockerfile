FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY director ./director
COPY contracts ./contracts
COPY solidity ./solidity

CMD ["python", "-m", "director.application"]