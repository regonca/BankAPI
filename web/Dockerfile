FROM python:3.11-slim
WORKDIR /usr/src/app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
# Download the InceptionV3 weights at build time so the container does not fetch them on every start
RUN python -c "from keras.applications import InceptionV3; InceptionV3(weights='imagenet')"
COPY . .
CMD [ "python", "./app.py" ]
