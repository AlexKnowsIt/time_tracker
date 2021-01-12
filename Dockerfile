FROM python:3

WORKDIR /usr/src/app

EXPOSE 8000
COPY . ./
RUN pip3 install -r requirements.txt
RUN python3 manage.py makemigrations
RUN python3 manage.py migrate

CMD [ "python3", "manage.py", "runserver" , "0.0.0.0:8000"]

# autobuilds enabled