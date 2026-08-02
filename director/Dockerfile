FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

RUN python -c "from solcx import install_solc; install_solc('0.8.20')"

COPY director ./director
COPY contracts ./contracts

CMD ["python", "-m", "director.application"]