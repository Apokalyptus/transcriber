FROM archlinux:latest

ENV HSA_OVERRIDE_GFX_VERSION=10.3.0

# Systempakete installieren
RUN pacman -Syu --noconfirm && \
    pacman -S --noconfirm \
        ca-certificates \
        git \
        base-devel \
        ffmpeg \
        python \
        python-setuptools \
        opencl-headers \
        rocm-opencl-runtime \
        vulkan-devel \
        clinfo \
        uv \
        curl \
        cmake

ENV UV_PROJECT_ENVIRONMENT=/app \
    VIRTUAL_ENV=/app
ENV PATH=$VIRTUAL_ENV/bin:$PATH

# Arbeitsverzeichnis
WORKDIR /app

# Projektdateien kopieren
COPY . .

# Venv erstellen mit uv und Abhängigkeiten installieren
RUN uv venv --python 3.11 --allow-existing --relocatable /app
RUN uv pip install --upgrade pip
RUN uv pip install -r requirements.txt


# whisper.cpp kompilieren
RUN git clone https://github.com/ggerganov/whisper.cpp.git 
RUN cd whisper.cpp && \
    cmake -B build -DGGML_VULKAN=1 -DWHISPER_FFMPEG=yes && \
    cmake --build build -j --config Release && \
    cp build/bin/whisper-cli /app/whisper-cli

# Port freigeben
EXPOSE 5000

# Anwendung starten über uv-venv
CMD ["/bin/bash", "-c", ". .venv/bin/activate && streamlit run app.py"]
