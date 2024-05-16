def read_photo(photo_name):
    with open(photo_name, 'rb') as new_file:
        return new_file.read()