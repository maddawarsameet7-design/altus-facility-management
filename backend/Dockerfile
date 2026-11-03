# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set work directory
WORKDIR /app

# Install dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . /app/

# Expose port
EXPOSE 8000

# Run entrypoint script (if any) or migration + server
CMD ["sh", "-c", "python manage.py collectstatic --noinput && python manage.py migrate && if [ \"$DEBUG\" = \"True\" ] || [ \"$DEBUG\" = \"true\" ] || [ \"$DEBUG\" = \"1\" ]; then python manage.py seed_data || true; fi && daphne -b 0.0.0.0 -p 8000 facility_proj.asgi:application"]
