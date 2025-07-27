FROM python:3.11

# This makes sure that logs show up immediately instead of being buffered
ENV PYTHONUNBUFFERED=1

RUN pip install --upgrade pip

# Install dagster and any other dependencies your project requires
RUN \
    pip install \
        dagster \
        dagster-postgres \
        dagster-k8s \
        # add any other dependencies here
        pandas \
        psycopg2-binary>=2.9.3

# Copy your Dagster project. You may need to replace the filepath depending on your project structure
COPY . /

WORKDIR /iris_analysis/

# Expose the port that your Dagster instance will run on
EXPOSE 80