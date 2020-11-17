FROM python:3.7-slim as py37-base
RUN apt -y update &&\
    apt-get install -y git &&\
    apt -y install build-essential &&\
    apt-get clean
WORKDIR /home/app

FROM py37-base as builder
COPY . .
RUN git config --global user.email "body@work.com" &&\
    git config --global user.name "bodywork"
RUN pip install -r requirements_dev.txt
RUN tox -e unit_and_functional_tests
RUN python setup.py bdist_wheel

FROM py37-base
COPY --from=builder /home/app/dist .
RUN pip install *.whl
ENTRYPOINT ["bodywork"]
CMD ["debug", "900"]
