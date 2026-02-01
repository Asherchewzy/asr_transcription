## sample files for additional testing

reference: https://www.kaggle.com/datasets/etaifour/trump-speeches-audio-and-word-transcription/data

Code to split 20 five‑second MP3s from main data:
```bash
ffmpeg -y -i sample_data/Trump_WEF_2018.mp3 \
  -t 100 -f segment -segment_time 5 -c copy \
  sample_data/Trump_WEF_2018_part%02d.mp3

```
