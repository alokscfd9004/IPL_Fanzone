FROM python:3.11

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir -r requirements.txt

RUN python manage.py collectstatic --noinput

ENV PORT 8080

CMD ["gunicorn", "--bind", "0.0.0.0:8080", "projectname.wsgi:application"]