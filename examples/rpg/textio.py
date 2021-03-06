import crayons

from wecs.core import Component
from wecs.core import System
from wecs.core import and_filter
from wecs.core import or_filter
from wecs.rooms import Room
from wecs.rooms import RoomPresence
from wecs.rooms import ChangeRoomAction
from wecs.inventory import Inventory
from wecs.inventory import TakeAction
from wecs.inventory import DropAction
from wecs.inventory import can_drop
from wecs.inventory import can_take
from wecs.equipment import Equipment
from wecs.equipment import Slot
from wecs.equipment import EquipAction
from wecs.equipment import UnequipAction
from wecs.equipment import can_equip
from wecs.equipment import can_unequip

from lifecycle import Alive
from lifecycle import Health
from lifecycle import Dead
from lifecycle import Undead
from magic import Mana
from magic import spells
from magic import SpellcastingMixin
from aging import Age
from character import Name
from dialogue import TalkAction


# This component will try trigger printin data about itself, but it
# needs at least a Name and some component it knows how to print as
# enablers.
@Component()
class Output:
    pass


# This component will make a system ask for command input. Needs two
# enablers, Name (to query for the character to control) and Action
# (to store the given command).
@Component()
class Input:
    pass


class TextOutputMixin():
    def textual_entity_state(self, entity):
        o = "" # Output accumulator

        # Name
        if entity.has_component(Name):
            name = entity.get_component(Name).name
        else:
            name = "Avatar"

        # Lifecycle status
        if entity.has_component(Alive):
            o += "{} is alive.\n".format(name)
        if entity.has_component(Dead):
            o += "{} is dead.\n".format(name)
        if entity.has_component(Undead):
            o += "{} is undead.\n".format(name)

        # Age
        if entity.has_component(Age):
            age = entity.get_component(Age).age
            frailty = entity.get_component(Age).age_of_frailty
            o += "{}'s age: ".format(name)
            o += "{}/{}".format(age, frailty)
            if age >= frailty:
                o += " (frail)"
            o += "\n"

        # Health
        if entity.has_component(Health):
            o += "{}'s health: {}/{}.\n".format(
                entity.get_component(Name).name,
                entity.get_component(Health).health,
                entity.get_component(Health).max_health,
            )

        # Mana
        if entity.has_component(Mana):
            o += "{}'s mana: {}/{}.\n".format(
                entity.get_component(Name).name,
                entity.get_component(Mana).mana,
                entity.get_component(Mana).max_mana,
            )

        # Castable spells
        if entity.has_component(Mana):
            readied_spells = entity.get_component(Mana).spells_ready
            o += "{} can cast: {}\n".format(
                entity.get_component(Name).name,
                ', '.join(spell.name for spell in readied_spells),
            )
        return o

    def textual_room_state(self, entity):
        o = "" # Output accumulator

        # Name
        if entity.has_component(Name):
            name = entity.get_component(Name).name
        else:
            name = "Avatar"

        # Presence in a room
        if not entity.has_component(RoomPresence):
            o += "{} is not anywhere.\n".format(name)
            return o

        # The room itself
        room_ref = entity.get_component(RoomPresence).room
        room = self.world.get_entity(room_ref)
        if not room.has_component(Name):
            o += "{} is in a nameless room\n".format(name)
        else:
            room_name = room.get_component(Name).name
            o += "{} is the room '{}'\n".format(name, room_name)

        # Other presences in the room
        presences = entity.get_component(RoomPresence).presences
        if presences:
            names = []
            for idx, presence in enumerate(presences):
                present_entity = self.world.get_entity(presence)
                if present_entity.has_component(Name):
                    names.append("({}) {}".format(
                        str(idx),
                        present_entity.get_component(Name).name,
                    ))
            o += "In the room are: {}\n".format(', '.join(names))

        # Adjacent rooms
        nearby_rooms = room.get_component(Room).adjacent
        nearby_room_names = []
        for idx, nearby_room in enumerate(nearby_rooms):
            nearby_room_entity = self.world.get_entity(nearby_room)
            if nearby_room_entity.has_component(Name):
                nearby_room_names.append("({}) {}".format(
                    str(idx),
                    nearby_room_entity.get_component(Name).name,
                ))
            else:
                nearby_room_names.append("({}) (unnamed)".format(str(idx)))
        o += "Nearby rooms: {}\n".format(', '.join(nearby_room_names))

        return o

    def print_entity_state(self, entity):
        o = self.textual_entity_state(entity)
        print(o)
        # If we have written any text yet, let's add a readability
        # newline.
        if o != "":
            o += "\n"

        o = self.textual_room_state(entity)
        print(o)
        # If we have written any text yet, let's add a readability
        # newline.
        if o != "":
            o += "\n"


class Shell(SpellcastingMixin, TextOutputMixin, System):
    entity_filters = {
        'outputs': and_filter([Output]),
        'inputs': and_filter([Input])
    }

    def update(self, filtered_entities):
        # First, produce output and get input for the outputter if it
        # is also an inputter.
        outputters = filtered_entities['outputs']
        for entity in outputters:
            self.print_entity_state(entity)
            if entity in filtered_entities['inputs']:
                self.shell(entity)
        # Also give the actors without output a shell
        actors = filtered_entities['inputs']
        for entity in [e for e in actors if e not in outputters]:
            self.shell(entity)

    def shell(self, entity):
        if entity.has_component(Name):
            name = entity.get_component(Name).name
        else:
            name = "Avatar"
        query = "Command for {}: ".format(
            name,
        )
        while not self.run_command(input(crayons.red(query)), entity):
            pass

    def run_command(self, command, entity):
        if entity.has_component(Dead):
            print("You are dead. You do nothing.")
            return True
        elif command == "":
            print("You do nothing.")
            return True
        elif command in ("i", "inventory"):
            self.show_equipment(entity)
            self.show_inventory(entity)
            return False # Instant action
        elif command.startswith("look "):
            self.look_at(entity, int(command[5:]))
            return False # Instant action
        elif command.startswith("take "):
            return self.take_command(entity, int(command[5:]))
        elif command.startswith("drop "):
            return self.drop_command(entity, int(command[5:]))
        elif command.startswith("equip "):
            return self.equip_command(entity, command[6:])
        elif command.startswith("unequip "):
            return self.unequip_command(entity, command[8:])
        elif command.startswith("go "):
            return self.change_room_command(entity, int(command[3:]))
        elif command.startswith("talk "):
            return self.talk_command(entity, int(command[5:]))
        elif command.startswith("cast "):
            return self.cast_command(entity, command[5:])

        print("Unknown command \"{}\"".format(command))
        return False

    def take_command(self, entity, object_id):
        if not entity.has_component(RoomPresence):
            print("Can't take objects from the roomless void.")
            return False
        presences = entity.get_component(RoomPresence).presences

        item = self.world.get_entity(presences[object_id])
        if can_take(item, entity):
            entity.add_component(TakeAction(item=item._uid))
            return True

        return False

    def drop_command(self, entity, object_id):
        # If I have an inventory...
        if not entity.has_component(Inventory):
            print("{} has no inventory.".format(name))
            return False

        inventory = entity.get_component(Inventory).contents
        item = self.world.get_entity(inventory[object_id])

        if can_drop(item, entity):
            entity.add_component(DropAction(item=item._uid))
            return True

        return False

    def equip_command(self, entity, code):
        item_id, _, slot_id = code.partition(" ")
        if item_id.startswith("r"):
            in_room = True
        elif item_id.startswith("i"):
            in_room = False
        else:
            print("Invalid item location, which must start with 'r' or 'i'.")
            return False

        item_idx = int(item_id[1:])
        if in_room:
            item_uid = entity.get_component(RoomPresence).presences[item_idx]
        else:
            item_uid = entity.get_component(Inventory).contents[item_idx]
        item = self.world.get_entity(item_uid)

        slot_idx = int(slot_id)
        slot_uid = entity.get_component(Equipment).slots[slot_idx]
        slot = self.world.get_entity(slot_uid)
        if not can_equip(item, slot, entity):
            print("Can't equip.")
            return False

        entity.add_component(EquipAction(item=item_uid, slot=slot_uid))
        return True

    def unequip_command(self, entity, code):
        slot_id, _, target_id = code.partition(" ")
        if target_id == "r":
            target = self.world.get_entity(
                entity.get_component(RoomPresence).room,
            )
        elif target_id == "i":
            target = entity
        else:
            print("Invalid target location, must be 'r' or 'i'.")
            return False

        slot_idx = int(slot_id)
        slot_uid = entity.get_component(Equipment).slots[slot_idx]

        entity.add_component(UnequipAction(slot=slot_uid, target=target._uid))
        return True

    def change_room_command(self, entity, target_idx):
        if not entity.has_component(RoomPresence):
            print("You have no presence that could be somewhere.")
            return False

        room_e = self.world.get_entity(entity.get_component(RoomPresence).room)
        room = room_e.get_component(Room)
        if target_idx < 0 or target_idx > len(room.adjacent):
            print("No such room.")
            return False

        target = room.adjacent[target_idx]
        entity.add_component(ChangeRoomAction(room=target))
        return True

    def talk_command(self, entity, target_idx):
        # FIXME: Sooo many assumptions in this line...
        talker = entity.get_component(RoomPresence).presences[target_idx]
        entity.add_component(TalkAction(talker=talker))
        return True

    def cast_command(self, entity, spell_name):
        for spell in spells:
            if spell.name == spell_name:
                if self.can_cast(entity, spell):
                    entity.add_component(spell.casting_action())
                    return True
                else:
                    return False

        print("No such spell exists.")
        return False

    def show_equipment(self, entity):
        if entity.has_component(Name):
            name = entity.get_component(Name).name
        else:
            name = "Avatar"

        if not entity.has_component(Equipment):
            print("{} has no equipment slots.".format(name))
            return False

        slots = [self.world.get_entity(e)
                 for e in entity.get_component(Equipment).slots]

        for idx, slot in enumerate(slots):
            slot_cmpt = slot.get_component(Slot)
            slot_name = slot_cmpt.type.name

            item = slot_cmpt.content
            if item is None:
                item_name = "(empty)"
            else:
                item_e = self.world.get_entity(slot_cmpt.content)
                if item_e.has_component(Name):
                    item_name = item_e.get_component(Name).name
                else:
                    item_name = "(no description)"

            print("(Slot {}: {}) {}".format(idx, slot_name, item_name))

    def show_inventory(self, entity):
        if entity.has_component(Name):
            name = entity.get_component(Name).name
        else:
            name = "Avatar"

        if not entity.has_component(Inventory):
            print("{} has no inventory.".format(name))
            return False

        # FIXME: try/except NoSuchUID:
        contents = [self.world.get_entity(e)
                    for e in entity.get_component(Inventory).contents]
        if len(contents) == 0:
            print("{}'s inventory is empty".format(name))
            return False

        content_names = []
        for idx, content in enumerate(contents):
            if content.has_component(Name):
                content_names.append(
                    "({}) {}".format(
                        str(idx),
                        content.get_component(Name).name,
                    )
                )
            else:
                content_names.append("({}) (unnamed)".format(str(idx)))

        for entry in content_names:
            print(entry)
        return True

    def look_at(self, entity, lookee_idx):
        if not entity.has_component(RoomPresence):
            print("You are nowhere, so there's nothing to look at.")
            return False
        presences = entity.get_component(RoomPresence).presences

        if lookee_idx < 0 or lookee_idx > len(presences):
            print("Invalid room presence id.")
            return False
        lookee = self.world.get_entity(presences[lookee_idx])

        o = self.textual_entity_state(lookee)
        if o == "":
            print("There's nothing there to look at.")
            return False

        print(o)
        return True
