FROM public.ecr.aws/docker/library/python:3.11-slim

COPY Pipfile* .
RUN pip install --upgrade pip pipenv
RUN pipenv install --system
RUN groupadd -g 10001 app && \
    useradd -r -u 10001 -g app app && \
    mkdir /usr/app && chown app:app /usr/app
WORKDIR /usr/app
COPY . /usr/app
USER app

# Add and run python app
COPY meraki_api_exporter.py .
ENTRYPOINT ["python", "meraki_api_exporter.py"]
CMD []
