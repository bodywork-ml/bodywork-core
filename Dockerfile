# bodywork - MLOps on Kubernetes.
# Copyright (C) 2020-2021  Bodywork Machine Learning Ltd.

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

FROM python:3.8-slim as py38-base
RUN apt -y update &&\
    apt-get install -y git &&\
    apt -y install build-essential &&\
    apt-get clean
WORKDIR /home/app

FROM py38-base as builder
COPY . .
RUN git config --global user.email "body@work.com" &&\
    git config --global user.name "bodywork"
RUN pip install -r requirements_dev.txt
RUN tox -e unit_and_functional_tests
RUN python setup.py bdist_wheel

FROM py38-base
COPY --from=builder /home/app/dist/*.whl .
RUN pip install *.whl &&\
    rm *.whl
ENTRYPOINT ["bodywork"]
CMD ["debug", "900"]
