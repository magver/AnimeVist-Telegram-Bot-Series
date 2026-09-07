FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV PORT=7860

COPY . /app

EXPOSE 7860

CMD ["python", "run_bot.py"]
