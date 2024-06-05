def get_user_by_chat_id(user_dict, chat_id):
    for key in user_dict.keys():
        if chat_id == user_dict[key].chat_ids:
            return key, user_dict[key]
    return (None, None)

def read_photo(photo_name):
    with open(photo_name, 'rb') as new_file:
        return new_file.read()