"""Legacy desktop panel for opening-theory trees.

This is intentionally a simple Tkinter tree-control panel. It is not the final
360° graph/map renderer; it exercises the theory service and keeps the visual
map free to evolve later.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, simpledialog
from typing import Callable, Dict, Optional

from neuralcheck.application.theory_controller import TheoryController
from neuralcheck.theory.models import TheoryBranch, TheoryBook, TheoryNode


class TheoryWindow:
    """Small CRUD/navigation window for local theory trees."""

    def __init__(
        self,
        master: tk.Misc,
        controller: TheoryController,
        on_board_changed: Optional[Callable[[], None]] = None,
        on_close: Optional[Callable[[], None]] = None,
    ):
        self.master = master
        self.controller = controller
        self.on_board_changed = on_board_changed
        self.on_close = on_close
        self.book_index: Dict[int, str] = {}
        self.child_index: Dict[int, str] = {}

        self.window = tk.Toplevel(master)
        self.window.title("Teoría")
        self.window.geometry("760x480")
        self.window.minsize(680, 420)
        self.window.protocol("WM_DELETE_WINDOW", self.close)

        self._build_layout()
        self.refresh_books()
        self.refresh_node_panel()

    def exists(self) -> bool:
        return bool(self.window.winfo_exists())

    def focus(self) -> None:
        self.window.lift()
        self.window.focus_force()

    def close(self) -> None:
        if self.on_close is not None:
            self.on_close()
        self.window.destroy()

    def _build_layout(self) -> None:
        self.window.rowconfigure(0, weight=1)
        self.window.columnconfigure(0, weight=0)
        self.window.columnconfigure(1, weight=1)

        self.books_frame = tk.LabelFrame(self.window, text="Entradas")
        self.books_frame.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        self.books_frame.rowconfigure(0, weight=1)
        self.books_frame.columnconfigure(0, weight=1)

        self.book_list = tk.Listbox(self.books_frame, width=28, height=18)
        self.book_list.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        self.book_list.bind("<<ListboxSelect>>", self._on_book_select)

        book_buttons = tk.Frame(self.books_frame)
        book_buttons.grid(row=1, column=0, sticky="ew", padx=4, pady=4)
        tk.Button(book_buttons, text="Nueva", command=self.create_book).grid(row=0, column=0, padx=2, pady=2)
        tk.Button(book_buttons, text="Raíz desde tablero", command=self.create_root_from_board).grid(row=0, column=1, padx=2, pady=2)
        tk.Button(book_buttons, text="Borrar", command=self.delete_selected_book).grid(row=0, column=2, padx=2, pady=2)

        self.node_frame = tk.LabelFrame(self.window, text="Nodo seleccionado")
        self.node_frame.grid(row=0, column=1, sticky="nsew", padx=8, pady=8)
        self.node_frame.rowconfigure(6, weight=1)
        self.node_frame.columnconfigure(1, weight=1)

        tk.Label(self.node_frame, text="Nombre:").grid(row=0, column=0, sticky="w", padx=4, pady=2)
        self.node_name = tk.StringVar(value="")
        tk.Label(self.node_frame, textvariable=self.node_name, anchor="w").grid(row=0, column=1, sticky="ew", padx=4, pady=2)

        tk.Label(self.node_frame, text="Turno:").grid(row=1, column=0, sticky="w", padx=4, pady=2)
        self.node_side = tk.StringVar(value="")
        tk.Label(self.node_frame, textvariable=self.node_side, anchor="w").grid(row=1, column=1, sticky="ew", padx=4, pady=2)

        tk.Label(self.node_frame, text="Origen:").grid(row=2, column=0, sticky="w", padx=4, pady=2)
        self.book_source = tk.StringVar(value="")
        tk.Label(self.node_frame, textvariable=self.book_source, anchor="w", wraplength=460).grid(row=2, column=1, sticky="ew", padx=4, pady=2)

        tk.Label(self.node_frame, text="FEN:").grid(row=3, column=0, sticky="nw", padx=4, pady=2)
        self.node_fen = tk.Text(self.node_frame, width=52, height=3, wrap=tk.WORD)
        self.node_fen.grid(row=3, column=1, sticky="ew", padx=4, pady=2)
        self.node_fen.config(state="disabled")

        nav_buttons = tk.Frame(self.node_frame)
        nav_buttons.grid(row=4, column=0, columnspan=2, sticky="ew", padx=4, pady=4)
        tk.Button(nav_buttons, text="Cargar nodo al tablero", command=self.load_selected_node_to_board).grid(row=0, column=0, padx=2, pady=2)
        tk.Button(nav_buttons, text="Subir al padre", command=self.open_parent_node).grid(row=0, column=1, padx=2, pady=2)
        tk.Button(nav_buttons, text="Eliminar rama", command=self.delete_selected_subtree).grid(row=0, column=2, padx=2, pady=2)

        child_form = tk.LabelFrame(self.node_frame, text="Agregar continuación por jugada")
        child_form.grid(row=5, column=0, columnspan=2, sticky="ew", padx=4, pady=4)
        child_form.columnconfigure(1, weight=1)
        child_form.columnconfigure(3, weight=1)

        tk.Label(child_form, text="Jugada:").grid(row=0, column=0, sticky="w", padx=2, pady=2)
        self.move_entry = tk.Entry(child_form, width=12)
        self.move_entry.grid(row=0, column=1, sticky="ew", padx=2, pady=2)
        tk.Label(child_form, text="Nombre:").grid(row=0, column=2, sticky="w", padx=2, pady=2)
        self.child_name_entry = tk.Entry(child_form, width=24)
        self.child_name_entry.grid(row=0, column=3, sticky="ew", padx=2, pady=2)
        tk.Button(child_form, text="Agregar", command=self.add_child_from_board).grid(row=0, column=4, padx=2, pady=2)

        tk.Label(self.node_frame, text="Continuaciones:").grid(row=6, column=0, sticky="nw", padx=4, pady=2)
        self.children_list = tk.Listbox(self.node_frame, width=52, height=10)
        self.children_list.grid(row=6, column=1, sticky="nsew", padx=4, pady=2)
        self.children_list.bind("<Double-Button-1>", self._on_child_double_click)

        child_buttons = tk.Frame(self.node_frame)
        child_buttons.grid(row=7, column=1, sticky="ew", padx=4, pady=4)
        tk.Button(child_buttons, text="Abrir continuación", command=self.open_selected_child).grid(row=0, column=0, padx=2, pady=2)
        tk.Button(child_buttons, text="Refrescar", command=self.refresh_all).grid(row=0, column=1, padx=2, pady=2)

    def refresh_all(self) -> None:
        self.refresh_books()
        self.refresh_node_panel()

    def refresh_books(self) -> None:
        selected_book_id = self.controller.selected_book_id
        self.book_index.clear()
        self.book_list.delete(0, tk.END)

        for index, book in enumerate(self.controller.list_books()):
            self.book_index[index] = book.id
            root_suffix = " ●" if book.root_node_id else ""
            source_suffix = " [línea sincronizada]" if book.is_synchronized_line else " [posición independiente]"
            self.book_list.insert(tk.END, f"{book.name}{root_suffix}{source_suffix}")
            if selected_book_id == book.id:
                self.book_list.selection_set(index)

    def refresh_node_panel(self) -> None:
        node = self.controller.get_selected_node()
        if node is None:
            self._set_node_text(None)
            self._refresh_children([])
            return

        self._set_node_text(node)
        self._refresh_children(self.controller.get_children(node.id))

    def create_book(self) -> None:
        name = simpledialog.askstring("Nueva entrada", "Nombre de la entrada:", parent=self.window)
        if name is None:
            return
        try:
            self.controller.create_book(name)
        except Exception as exc:
            messagebox.showerror("No se pudo crear la entrada", str(exc), parent=self.window)
            return
        self.refresh_all()

    def create_root_from_board(self) -> None:
        book_id = self._selected_book_id_from_list_or_controller()
        if book_id is None:
            messagebox.showwarning("Sin entrada", "Selecciona o crea una entrada primero.", parent=self.window)
            return
        name = simpledialog.askstring("Nodo raíz", "Nombre opcional de la raíz:", parent=self.window)
        try:
            self.controller.create_root_from_current_position(book_id, name=name)
        except Exception as exc:
            messagebox.showerror("No se pudo crear la raíz", str(exc), parent=self.window)
            return
        self.refresh_all()

    def delete_selected_book(self) -> None:
        book_id = self._selected_book_id_from_list_or_controller()
        if book_id is None:
            return
        if not messagebox.askyesno(
            "Borrar entrada",
            "Esto borrará la entrada completa y todas sus posiciones. ¿Continuar?",
            parent=self.window,
        ):
            return
        self.controller.delete_book(book_id)
        self.refresh_all()

    def add_child_from_board(self) -> None:
        node = self.controller.get_selected_node()
        if node is None:
            messagebox.showwarning("Sin nodo", "Selecciona un nodo padre primero.", parent=self.window)
            return

        move_san = self.move_entry.get().strip()
        name = self.child_name_entry.get().strip() or None
        if not move_san:
            messagebox.showwarning("Jugada requerida", "La relación necesita una jugada.", parent=self.window)
            return

        try:
            branch = self.controller.add_child_by_move(node.id, move_san=move_san, name=name)
            validation = self.controller.load_node_to_board(branch.node.id)
        except Exception as exc:
            messagebox.showerror("No se pudo agregar la continuación", str(exc), parent=self.window)
            return

        if not validation.valid:
            messagebox.showerror(
                "No se pudo sincronizar el tablero",
                "\n".join(validation.errors),
                parent=self.window,
            )
            return

        self.move_entry.delete(0, tk.END)
        self.child_name_entry.delete(0, tk.END)
        if self.on_board_changed is not None:
            self.on_board_changed()
        self.refresh_all()

    def open_selected_child(self) -> None:
        child_id = self._selected_child_id()
        if child_id is None:
            return
        self.controller.select_node(child_id)
        self.refresh_node_panel()

    def open_parent_node(self) -> None:
        branch = self.controller.get_parent_branch()
        if branch is None:
            return
        self.controller.select_node(branch.node.id)
        self.refresh_node_panel()

    def load_selected_node_to_board(self) -> None:
        node = self.controller.get_selected_node()
        if node is None:
            return
        validation = self.controller.load_node_to_board(node.id)
        if not validation.valid:
            messagebox.showerror(
                "No se pudo cargar la posición",
                "\n".join(validation.errors),
                parent=self.window,
            )
            return
        if self.on_board_changed is not None:
            self.on_board_changed()

    def delete_selected_subtree(self) -> None:
        node = self.controller.get_selected_node()
        if node is None:
            return
        preview = self.controller.preview_delete_subtree(node.id)
        labels = "\n".join(f"- {label}" for label in preview.labels[:12])
        if len(preview.labels) > 12:
            labels += f"\n- ... y {len(preview.labels) - 12} más"
        message = (
            f"Se borrarán {preview.node_count} nodo(s) y {preview.edge_count} relación(es).\n\n"
            f"{labels}\n\n¿Continuar?"
        )
        if not messagebox.askyesno("Borrar rama", message, parent=self.window):
            return
        self.controller.delete_subtree(node.id)
        if self.controller.selected_book_id is not None:
            self.controller.select_book(self.controller.selected_book_id)
        self.refresh_all()

    def _on_book_select(self, event) -> None:
        del event
        book_id = self._selected_book_id_from_list()
        if book_id is None:
            return
        self.controller.select_book(book_id)
        self.refresh_node_panel()

    def _on_child_double_click(self, event) -> None:
        del event
        self.open_selected_child()

    def _set_node_text(self, node: Optional[TheoryNode]) -> None:
        if node is None:
            self.node_name.set("Sin nodo seleccionado")
            self.node_side.set("")
            self.book_source.set(self.controller.selected_book_source_label())
            fen = ""
        else:
            self.node_name.set(node.name or "Sin nombre")
            self.node_side.set(node.side_to_move)
            self.book_source.set(self.controller.selected_book_source_label())
            fen = node.fen

        self.node_fen.config(state="normal")
        self.node_fen.delete("1.0", tk.END)
        if fen:
            self.node_fen.insert(tk.END, fen)
        self.node_fen.config(state="disabled")

    def _refresh_children(self, branches: list[TheoryBranch]) -> None:
        self.child_index.clear()
        self.children_list.delete(0, tk.END)
        for index, branch in enumerate(branches):
            self.child_index[index] = branch.node.id
            name = branch.node.name or branch.node.fen.split()[0][:24]
            self.children_list.insert(tk.END, f"{branch.edge.move_san} → {name}")

    def _selected_book_id_from_list(self) -> Optional[str]:
        selection = self.book_list.curselection()
        if not selection:
            return None
        return self.book_index.get(selection[0])

    def _selected_book_id_from_list_or_controller(self) -> Optional[str]:
        return self._selected_book_id_from_list() or self.controller.selected_book_id

    def _selected_child_id(self) -> Optional[str]:
        selection = self.children_list.curselection()
        if not selection:
            return None
        return self.child_index.get(selection[0])
