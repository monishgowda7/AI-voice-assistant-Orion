import numpy as np, sounddevice as sd
from resemblyzer import VoiceEncoder

SR = 16000
encoder = VoiceEncoder()
embeds = []

for i in range(5):
    input(f"Press Enter, then speak for 5 sec ({i+1}/5)...")
    audio = sd.rec(int(5 * SR), samplerate=SR, channels=1, dtype="float32")
    sd.wait()
    embeds.append(encoder.embed_utterance(audio.flatten()))

np.save("creater_voice.npy", np.mean(embeds, axis=0))
print("Saved.")