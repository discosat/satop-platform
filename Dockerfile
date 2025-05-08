FROM python:3.13

COPY . /app
RUN chmod -R 777 /app

RUN pip install --upgrade pip

ENV SATOP_DATA_ROOT=/satop/data
ENV SATOP_API__HOST=0.0.0.0
ENV SATOP_API__PORT=7889

RUN adduser runner
USER runner

RUN pip install --user /app

ENTRYPOINT [ "python", "-m", "satop_platform" ]