def no_authentication(func):
    func.no_authentication = True
    return func