# Use Python 3.12 slim image
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set work directory
WORKDIR /usr/src/app

# Install system dependencies
# RUN apt-get update \
#     # && apt-get install -y --no-install-recommends \
#     #     postgresql-client \
#     #     build-essential \
#     #     libpq-dev \
#     && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt /usr/src/app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . /usr/src/app/

# Create staticfiles directory
RUN mkdir -p /usr/src/app/staticfiles

# Collect static files
# RUN python manage.py collectstatic --noinput || true

# Expose port
EXPOSE 8000

# run the application
CMD ["gunicorn", "core.wsgi:application", "--bind", "0.0.0.0:8000"]