FROM python:3.12

COPY . /app

ENV SATOP_DATA_ROOT=/satop/data
ENV SATOP_API__HOST=0.0.0.0
ENV SATOP_API__PORT=7889

RUN pip install /app

ENTRYPOINT [ "python", "-m", "satop_platform" ]