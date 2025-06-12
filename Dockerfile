FROM python:3.13 AS base

RUN pip install --upgrade pip

ENV SATOP_DATA_ROOT=/satop/data
ENV SATOP_API__HOST=0.0.0.0
ENV SATOP_API__PORT=7889


FROM base AS deploy

COPY . /app
RUN chmod -R 777 /app

RUN adduser runner
USER runner

RUN ls -al /app

RUN pip install --user /app

ENTRYPOINT [ "python", "-m", "satop_platform" ]


FROM base AS devel

RUN mkdir /ws
RUN adduser devuser
RUN chown -R devuser:devuser /ws
USER devuser

ENV PATH=$PATH:/home/devuser/.local/bin

ENV SHELL=bash