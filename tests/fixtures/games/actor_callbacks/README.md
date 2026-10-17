# Actor callbacks

Run `plocks run tests/fixtures/games/actor_callbacks` from a checkout, or copy `main.py` into
your own project with Plocks installed and run `python main.py`. Artwork is
generated with Pillow; no asset files are required.

- Hold Left/Right to move the orange Sprite using its `on_update` callback.
- Click orange to run a block sequence; click blue for a synchronous callback.
- Click the green Puppet to show dialogue; it has its own update callback.
- Press P to pause/resume. Sync clicks and the global click counter still work
  while paused; movement and block execution wait for resume.

Only the topmost visible actor receives targeted clicks. Stage click observers
receive every click, including empty space. Register actor callbacks after
`stage.add(actor)`. Updates are synchronous and use fixed simulated seconds.
Custom drawing remains on Stage.
