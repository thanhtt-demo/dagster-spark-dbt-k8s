FROM public.ecr.aws/emr-on-eks/spark/emr-7.8.0

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

USER root
RUN mkdir /python && chown hadoop:hadoop /python

USER hadoop
ENV UV_PYTHON_INSTALL_DIR=/python \
    UV_BREAK_SYSTEM_PACKAGES=1

RUN uv python install --python-preference only-managed 3.9.16

ENV PATH="${UV_PYTHON_INSTALL_DIR}/cpython-3.9.16-linux-x86_64-gnu/bin:${PATH}" \
    PYTHONPATH="${UV_PYTHON_INSTALL_DIR}/cpython-3.9.16-linux-x86_64-gnu/lib/python3.9/site-packages" \
    UV_PYTHON="${UV_PYTHON_INSTALL_DIR}/cpython-3.9.16-linux-x86_64-gnu/bin/python" \
    PYSPARK_PYTHON="${UV_PYTHON_INSTALL_DIR}/cpython-3.9.16-linux-x86_64-gnu/bin/python" \
    PYSPARK_DRIVER_PYTHON="${UV_PYTHON_INSTALL_DIR}/cpython-3.9.16-linux-x86_64-gnu/bin/python"

RUN uv pip install dagster dagster-pipes boto3 pyspark pandas

# Copy your Dagster project. You may need to replace the filepath depending on your project structure
WORKDIR /app

COPY . .

# WORKDIR /iris_analysis/

# Expose the port that your Dagster instance will run on
EXPOSE 80