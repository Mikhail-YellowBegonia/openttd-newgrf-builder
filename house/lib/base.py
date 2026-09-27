import grf


class AHouse(grf.SpriteGenerator):
    def __init__(self, *, id, name, sprites, flags, callbacks={}, **props):
        super().__init__()
        self.id = id
        self.name = name
        self.sprites = sprites
        self.flags = flags
        self.callbacks = grf.make_callback_manager(grf.HOUSE, callbacks)
        self._props = props

    def get_sprites(self, g):
        res = []

        if self.sprites:
            layouts = []
            for i, sprite in enumerate(self.sprites):
                layouts.append(
                    grf.BasicSpriteLayout(
                        ground={"sprite": grf.SpriteRef(3924, is_global=True)},
                        building={
                            "sprite": grf.SpriteRef(i, is_global=False),
                            "offset": (0, 0),
                            "extent": (16, 16, 16),
                        },
                        feature=grf.HOUSE,
                    )
                )
            assert len(layouts) == 8
            self.callbacks.graphics = grf.RandomSwitch(
                feature=grf.HOUSE,
                scope="self",
                triggers=0,
                lowest_bit=0,
                cmp_all=False,
                groups=layouts,
            )

        res.append(
            definition := grf.Define(
                feature=grf.HOUSE,
                id=self.id,
                props={**self._props, "flags": self.flags},
            )
        )
        if self.sprites:
            res.append(
                grf.Action1(
                    feature=grf.HOUSE, set_count=len(self.sprites), sprite_count=1
                )
            )

            for s in self.sprites:
                res.append(s)

        res.extend(self.callbacks.make_map_action(definition))

        return res


class AMultiTileHouse(grf.SpriteGenerator):
    """A minimal contiguous multi-tile House definition.

    OpenTTD identifies a multi-tile house by a north tile with a size flag
    followed immediately by the east, west and south tile IDs.  The graphics
    sets are emitted as one Action 1 so each tile can point at its own eight
    directional sets.  The first tile may carry the complete building sprite;
    affiliated tiles can use transparent sprites when the source art is one
    full-canvas composition.
    """

    def __init__(self, *, id, name, tile_sprites, flags, substitute_ids, **props):
        super().__init__()
        if len(tile_sprites) != 4 or any(len(s) != 8 for s in tile_sprites):
            raise ValueError("a 2x2 house needs four groups of eight sprites")
        self.id = id
        self.name = name
        self.tile_sprites = tile_sprites
        self.flags = flags
        self.substitute_ids = substitute_ids
        self._props = props

    def get_sprites(self, g):
        layouts = []
        for tile_index in range(4):
            callbacks = grf.make_callback_manager(grf.HOUSE, {})
            groups = []
            base = tile_index * 8
            for i in range(8):
                groups.append(
                    grf.BasicSpriteLayout(
                        ground={"sprite": grf.SpriteRef(3924, is_global=True)},
                        building={
                            "sprite": grf.SpriteRef(base + i, is_global=False),
                            "offset": (0, 0),
                            "extent": (16, 16, 16),
                        },
                        feature=grf.HOUSE,
                    )
                )
            callbacks.graphics = grf.RandomSwitch(
                feature=grf.HOUSE,
                scope="self",
                triggers=0,
                lowest_bit=0,
                cmp_all=False,
                groups=groups,
            )
            props = {
                **self._props,
                "substitute": self.substitute_ids[tile_index],
                "flags": self.flags if tile_index == 0 else 0,
            }
            if tile_index != 0:
                # Affiliated tiles are not independently buildable and do not
                # contribute population; the north tile owns the building's
                # town effects.
                props["availability_mask"] = 0
                props["population"] = 0
                props["probability"] = 0
            definition = grf.Define(
                feature=grf.HOUSE,
                id=self.id + tile_index,
                props=props,
            )
            layouts.append((definition, callbacks))

        result = [definition for definition, _ in layouts]
        result.append(grf.Action1(feature=grf.HOUSE, set_count=32, sprite_count=1))
        result.extend(sprite for group in self.tile_sprites for sprite in group)
        for definition, callbacks in layouts:
            result.extend(callbacks.make_map_action(definition))
        return result
