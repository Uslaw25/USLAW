FROM python:3.13-bookworm

ENV PYTHONUNBUFFERED=1
ENV POETRY_VERSION=1.8.3
ENV POETRY_HOME=/opt/poetry
ENV POETRY_VIRTUALENVS_CREATE=false
ENV PATH="$POETRY_HOME/bin:$PATH"

RUN apt update && apt install -y curl && apt clean

RUN #curl -sSL https://install.python-poetry.org | python3 -
RUN pip install poetry==2.2

RUN mkdir /code
WORKDIR /code

COPY pyproject.toml poetry.lock README.md /code/

RUN poetry install --no-interaction --no-ansi --no-root

#RUN poetry install

# Copy the rest of the application code
COPY . /code/

# Expose the port
EXPOSE 8000

# Set the default command to run the FastAPI app (using app/main.py as the entrypoint)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
