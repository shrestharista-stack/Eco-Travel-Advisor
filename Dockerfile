FROM python:3.8-slim

WORKDIR /app

# install rasa and other dependencies
RUN pip install rasa==3.1.0 rasa-sdk requests streamlit

# copy all the project files into the container
COPY config.yml domain.yml endpoints.yml credentials.yml ./
COPY data/ ./data/
COPY actions.py ./
COPY app.py ./
COPY mock_data/ ./mock_data/
COPY models/ ./models/

# expose the ports for rasa server, action server, and streamlit
EXPOSE 5005 5055 8501

# default command starts the rasa server
CMD ["rasa", "run", "--enable-api", "--cors", "*", "--port", "5005"]
