from dataclasses import dataclass
import typing


@dataclass
class Layer:
    name: str
    colour: typing.Union[typing.List, str, int] = None
    ltype: str = None
    lweight: str = None

    def __post_init__(self):
        bad_characters = ["\\", "/"]
        for i in bad_characters:
            self.name = self.name.replace(i, "_")

    def ACAD(self) -> typing.List[str]:
        """Produces a list of commands to create a layer in AutoCAD"""
        command = []
        command.append("_.-LAYER")
        command.append(f'M "{self.name}"')
        if self.colour:
            try:
                if type(self.colour) == int or type(self.colour) == float:
                    self.colour = int(self.colour)
                    if self.colour <= 255:
                        command.append(f'C {self.colour} "{self.name}"')
                    else:
                        command.append(f'C T {self.colour:,} "{self.name}"')

                if type(self.colour) == str:
                    if len(self.colour) <= 3:
                        command.append(f'C {self.colour} "{self.name}"')
                    else:
                        command.append(f'C T {self.colour} "{self.name}"')

                if type(self.colour) == list:
                    colour = ",".join([str(int(i)) for i in self.colour])
                    command.append(f'C T {colour} "{self.name}"')

            except Exception as e:
                print(e)

        if self.ltype:
            command.append(f'L {self.ltype} "{self.name}"')
        if self.lweight:
            command.append(f'LW {self.lweight} "{self.name}"')
        command.append("(SCRIPT-CANCEL)")
        return command

    def to_front(self) -> typing.List[str]:
        return [f'(ssget "X" \'((8 . "{self.name}")))\nDRAWORDER P\n\nF']

    def to_back(self) -> typing.List[str]:
        return [f'(ssget "X" \'((8 . "{self.name}")))\nDRAWORDER P\n\nB']

    def delete(self):
        return self.ACAD() + Layer("0").ACAD() + [f"_.-LAYDEL N {self.name}", "", "Y"]
