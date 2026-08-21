# Location scene images

The 3D world chart shows each location as a rounded photo card. Drop a square
PNG named after the location id here and it appears automatically (no code
changes needed):

```text
everstory/api/static/img/locations/
  lighthouse_ground.png   Lighthouse Ground Floor
  lighthouse_tower.png    Lighthouse Tower
  lantern_room.png        Lantern Room
  cottage.png             Keeper's Cottage
  dock.png                Dock
  boat_shed.png           Boat Shed
  cliff_path.png          Cliff Path
  cave.png                Sea Cave
  platform.png            Platform Nine        (Ghost Train)
  waiting_room.png        Waiting Room
  coach_a.png             Coach A
  coach_b.png             Coach B
  dining_car.png          Dining Car
  locomotive.png          Locomotive
  caboose.png             Caboose
```

Until an image exists for a location, the chart falls back to the abstract
beacon circle. Images should be roughly square (1024x1024 works well) and
match the world's moody, night-time art direction.
