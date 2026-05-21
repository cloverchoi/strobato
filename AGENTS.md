# Strobato Project Instructions

Strobato is an SDK-first MusicTech project.

## Product Direction

- Build a software add-on that other digital sheet music apps can integrate.
- Do not build a standalone sheet music app.
- Focus on score synchronization: current measure tracking and page-turn signaling.
- Keep the first product wedge small enough to prove the core idea clearly.

## MVP Priorities

1. MusicXML parsing
2. Simulated note matching
3. Current measure inference
4. Page-turn signaling
5. Real audio input later

Do simulated note matching before live microphone input.

## Code Style

- Keep code beginner-friendly and easy to read.
- Prefer small modules with plain names.
- Add comments only when they make the logic easier to understand.
- Do not add infrastructure before it is needed.
- Do not optimize for scale yet.

## Things To Avoid

- Do not overbuild.
- Do not add a full app or frontend unless explicitly requested.
- Do not add microphone input until simulated score following works well.
- Do not introduce heavy dependencies for the first MVP unless they clearly solve an immediate problem.
