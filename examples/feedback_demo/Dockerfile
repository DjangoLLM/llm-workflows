FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN python -m pip install --upgrade pip

COPY pyproject.toml /app/pyproject.toml
COPY README.md /app/README.md

RUN pip install \
    Django==4.2.27 \
    djangorestframework==3.15.2 \
    pydantic-ai==1.34.0 \
    temporalio>=1.18.0

COPY . /app

RUN pip install -e /app --no-deps

WORKDIR /app/examples/feedback_demo

EXPOSE 8000
