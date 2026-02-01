## Additional sample files on top of 3 samples for additional testing
These are additional files used to test the app on top of the 3 sample files. 
They are snippets of a single larger file that can be used to test larger file and larger batch size behaviors. 

```bash
# Code to split 20 five‑second MP3s from main data:
ffmpeg -y -i sample_data/Trump_WEF_2018.mp3 \
  -t 100 -f segment -segment_time 5 -c copy \
  sample_data/Trump_WEF_2018_part%02d.mp3

```

**Reference:** https://www.kaggle.com/datasets/etaifour/trump-speeches-audio-and-word-transcription/data
