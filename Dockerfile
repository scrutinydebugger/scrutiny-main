FROM ubuntu:22.04 as build-tests

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    git \
    wget \
    libssl-dev \
    build-essential \
    clang \
    libffi-dev \
    libreadline-dev \
    zlib1g-dev \
    libsqlite3-dev \
    gcc-avr \
    libglib2.0-dev  \
    gcc-arm-none-eabi   \
    iproute2 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /tmp/


# ============================================
ARG PYTHON_VERSION="3.13.12"
ARG PYTHON_SRC="https://www.python.org/ftp/python/${PYTHON_VERSION}/Python-${PYTHON_VERSION}.tgz"

RUN wget $PYTHON_SRC \
    && tar -xvzf "Python-${PYTHON_VERSION}.tgz" \
    && cd "Python-${PYTHON_VERSION}" \
    && ./configure \
    && make -j 4 \
    && make install \
    && cd .. \
    && rm "Python-${PYTHON_VERSION}.tgz" \
    && rm -rf "Python-${PYTHON_VERSION}"

# ============================================
ARG PYTHON_VERSION="3.12.13"
ARG PYTHON_SRC="https://www.python.org/ftp/python/${PYTHON_VERSION}/Python-${PYTHON_VERSION}.tgz"

RUN wget $PYTHON_SRC \
    && tar -xvzf "Python-${PYTHON_VERSION}.tgz" \
    && cd "Python-${PYTHON_VERSION}" \
    && ./configure \
    && make -j 4 \
    && make install \
    && cd .. \
    && rm "Python-${PYTHON_VERSION}.tgz" \
    && rm -rf "Python-${PYTHON_VERSION}"

# ============================================
ARG PYTHON_VERSION="3.11.15"
ARG PYTHON_SRC="https://www.python.org/ftp/python/${PYTHON_VERSION}/Python-${PYTHON_VERSION}.tgz"

RUN wget $PYTHON_SRC \
    && tar -xvzf "Python-${PYTHON_VERSION}.tgz" \
    && cd "Python-${PYTHON_VERSION}" \
    && ./configure \
    && make -j 4 \
    && make install \
    && cd .. \
    && rm "Python-${PYTHON_VERSION}.tgz" \
    && rm -rf "Python-${PYTHON_VERSION}"


# ============================================
ARG PYTHON_VERSION="3.10.20"
ARG PYTHON_SRC="https://www.python.org/ftp/python/${PYTHON_VERSION}/Python-${PYTHON_VERSION}.tgz"

RUN wget $PYTHON_SRC \
    && tar -xvzf "Python-${PYTHON_VERSION}.tgz" \
    && cd "Python-${PYTHON_VERSION}" \
    && ./configure \
    && make -j 4 \
    && make install \
    && cd .. \
    && rm "Python-${PYTHON_VERSION}.tgz" \
    && rm -rf "Python-${PYTHON_VERSION}"



# Enable QT for Python inside Docker given that QT_QPA_PLATFORM='offscreen'
RUN apt-get update && apt-get install -y \
    libgl1 \
    libegl1 \
    libxkbcommon-x11-0 \
    libfontconfig1 \
    libdbus-glib-1-dev  \
    && rm -rf /var/lib/apt/lists/*

## TEMP for building PySide and debugging


RUN apt-get update && apt-get install -y \
    gdb     \
    p7zip   \
    cmake   \
    && rm -rf /var/lib/apt/lists/*

RUN wget "https://scrutinydebugger.com/qt6.9.tar.gz" \
    && tar -xvzf qt6.9.tar.gz

RUN wget "https://download.qt.io/development_releases/prebuilt/libclang/libclang-release_18.1.5-based-linux-Ubuntu22.04-gcc11.4-x86_64.7z"  \
    && 7z x libclang-release_18.1.5-based-linux-Ubuntu22.04-gcc11.4-x86_64.7z

ENV LLVM_INSTALL_DIR=/tmp/libclang

RUN python3.13 -m venv /tmp/venv_test3.13 && source venv_test3.13/bin/activate && pip install setuptools

RUN git clone https://code.qt.io/pyside/pyside-setup    \
    cd pyside-setup                                     \
    git checkout 6.9.0

RUN python setup.py install --qtpaths=/tmp/Qt6.9/6.9.3/gcc_64/bin/qtpaths6 \
                        --ignore-git \
                        --debug \
                        --build-tests \
                        --parallel=8 \
                        --verbose-build \
                        --build-type=all \
                        --module-subset=Core,Gui,Widgets,Charts
