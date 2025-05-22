FROM archlinux:latest

ENV HSA_OVERRIDE_GFX_VERSION=10.3.0

# Systempakete installieren
RUN pacman -Syu --noconfirm && \
    pacman -S --noconfirm \
        git \
        base-devel \
        ffmpeg \
        python \
        opencl-headers \
        rocm-opencl-runtime \
        clinfo \
        uv \
        curl

# Arbeitsverzeichnis
WORKDIR /app

# Projektdateien kopieren
COPY . .

# Venv erstellen mit uv und Abhängigkeiten installieren
RUN uv venv .venv && \
    uv pip install --upgrade pip && \
    uv pip install -r requirements.txt

# whisper.cpp kompilieren
RUN git clone https://github.com/ggerganov/whisper.cpp.git \
    #&& cd whisper.cpp && make && cp main /app/main
    && cmake -B build -DGGML_VULKAN=1 -DWHISPER_FFMPEG=yes \
    && cmake --build build -j --config Release \
    && cp build/bin/whisper-cli /app/whisper-cli \


# Port freigeben
EXPOSE 5000

# Anwendung starten über uv-venv
CMD ["/bin/bash", "-c", ". .venv/bin/activate && python app.py"]
