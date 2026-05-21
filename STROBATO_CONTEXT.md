# STROBATO CONTEXT

Strobato is NOT a standalone sheet music app.

Strobato is an SDK/software add-on that digital sheet music apps integrate.

The SDK listens to live music and synchronizes the score in real time.

The first wedge is:
- automatic page turning
- current measure tracking
- live score following

Core flow:

live music
→ note detection
→ compare to score
→ infer measure position
→ send synchronization signal
→ sheet music app updates UI

The first MVP should:
- use MusicXML
- support piano first
- work in real time
- estimate current measure
- send page-turn signals

Do NOT overbuild.

Focus only on proving synchronization works.

The company should be positioned as:
"AI synchronization infrastructure for digital sheet music platforms."
