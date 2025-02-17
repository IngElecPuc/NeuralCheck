
class Explorer:
    def __init__(self):
        pass

    def show_attributes(self, obj, show_value=False):
        print(f"Atributos de la clase {obj.__class__.__name__}:")
    
        # Atributos de la instancia
        print("\n🔹 Atributos de instancia:")
        for attr, value in obj.__dict__.items():
            if show_value:
                print(f"  - {attr}: {value}")
            else:
                print(f"  - {attr}")
        
        # Atributos de la clase
        print("\n🔹 Atributos de clase:")
        for attr in dir(obj):
            if not attr.startswith("__") and not callable(getattr(obj, attr)):
                print(f"  - {attr}: {getattr(obj, attr)}")

    def show_methods(self, obj):
        print(f"Métodos de la clase {obj.__class__.__name__}:")

        # Filtrar métodos con dir() y callable()
        metodos = [attr for attr in dir(obj) if callable(getattr(obj, attr)) and not attr.startswith("__")]

        if metodos:
            for metodo in metodos:
                print(f"  - {metodo}()")
        else:
            print("  (No tiene métodos visibles)")