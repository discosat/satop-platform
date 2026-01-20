FROM python:3.13 AS base

RUN pip install --upgrade pip

ENV SATOP_DATA_ROOT=/satop/data
ENV SATOP_API__HOST=0.0.0.0
ENV SATOP_API__PORT=7889


FROM base AS deploy

WORKDIR /satop

COPY . .

RUN adduser --system --group runner
RUN chown runner:runner /satop -R

RUN pip install --no-cache-dir .

USER runner

ENTRYPOINT [ "python", "-m", "satop_platform"]


FROM base AS devel

WORKDIR /satop

COPY pyproject.toml ./

RUN pip install --no-cache-dir -e '.[lint,test]'

COPY . .


RUN adduser --disabled-password --gecos "" devuser && \
    chown -R devuser:devuser /satop
