import sys

from nbt import nbt  # type: ignore
from nbt.nbt import TAG, TAG_Compound, TAG_List  # type: ignore


def print_tag(tag: TAG, indent: int = 0) -> None:
    """Recursively print an NBT tag and its contents."""
    indent_str: str = "  " * indent

    if isinstance(tag, TAG_Compound):
        print(f'{indent_str}TAG_Compound("{tag.name}")')
        for child in tag.tags:
            print_tag(child, indent + 1)

    elif isinstance(tag, TAG_List):
        print(f'{indent_str}TAG_List("{tag.name}") [{len(tag)} items]')
        for i, item in enumerate(tag):
            print(f"{indent_str}  [index {i}]")
            print_tag(item, indent + 2)

    else:
        print(f'{indent_str}{tag.__class__.__name__}("{tag.name}"): {tag.value}')


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python nbt_print.py <filename>")
        return

    filename: str = sys.argv[1]
    try:
        nbtfile: nbt.NBTFile = nbt.NBTFile(filename, "rb")
        print_tag(nbtfile)
    except Exception as e:
        print(f"Failed to read NBT file: {e}")


if __name__ == "__main__":
    main()
