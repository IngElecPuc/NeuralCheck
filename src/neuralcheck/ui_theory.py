"""Desktop panel for opening-theory tree CRUD and local navigation.

This window is still an intermediate controller, not the final visual graph map.
It presents a compact local view around the selected node: parent, current node,
siblings and children. The storage backend remains hidden behind
``TheoryController``.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import Callable, Dict, Optional

from neuralcheck.application.theory_controller import TheoryController
from neuralcheck.theory.models import TheoryBranch, TheoryLocalView, TheoryNode


class TheoryWindow:
    """CRUD/navigation window for local theory trees."""

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
        self.view_item_actions: Dict[str, tuple[str, str]] = {}

        self.window = tk.Toplevel(master)
        self.window.title("Teoría")
        self.window.geometry("980x620")
        self.window.minsize(860, 540)
        self.window.protocol("WM_DELETE_WINDOW", self.close)

        self._build_layout()
        self._bind_keys()
        self.refresh_all()

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

        self.book_list = tk.Listbox(self.books_frame, width=34, height=22)
        self.book_list.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        self.book_list.bind("<<ListboxSelect>>", self._on_book_select)

        book_buttons = tk.Frame(self.books_frame)
        book_buttons.grid(row=1, column=0, sticky="ew", padx=4, pady=4)
        tk.Button(book_buttons, text="Nueva", command=self.create_book).grid(row=0, column=0, padx=2, pady=2)
        tk.Button(book_buttons, text="Renombrar", command=self.rename_selected_book).grid(row=0, column=1, padx=2, pady=2)
        tk.Button(book_buttons, text="Raíz desde tablero", command=self.create_root_from_board).grid(row=1, column=0, columnspan=2, sticky="ew", padx=2, pady=2)
        tk.Button(book_buttons, text="Borrar entrada", command=self.delete_selected_book).grid(row=2, column=0, columnspan=2, sticky="ew", padx=2, pady=2)

        self.main_frame = tk.Frame(self.window)
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=8, pady=8)
        self.main_frame.rowconfigure(4, weight=1)
        self.main_frame.columnconfigure(0, weight=1)

        self.source_var = tk.StringVar(value="Sin entrada seleccionada")
        tk.Label(self.main_frame, textvariable=self.source_var, anchor="w", wraplength=660).grid(row=0, column=0, sticky="ew", padx=4, pady=(2, 4))

        self.path_var = tk.StringVar(value="Ruta: —")
        tk.Label(self.main_frame, textvariable=self.path_var, anchor="w", wraplength=660).grid(row=1, column=0, sticky="ew", padx=4, pady=(0, 4))

        self.node_frame = tk.LabelFrame(self.main_frame, text="Nodo seleccionado")
        self.node_frame.grid(row=2, column=0, sticky="ew", padx=4, pady=4)
        self.node_frame.columnconfigure(1, weight=1)
        self.node_frame.columnconfigure(3, weight=1)

        tk.Label(self.node_frame, text="Nombre:").grid(row=0, column=0, sticky="w", padx=4, pady=2)
        self.node_name_entry = tk.Entry(self.node_frame, width=28)
        self.node_name_entry.grid(row=0, column=1, sticky="ew", padx=4, pady=2)

        tk.Label(self.node_frame, text="Evaluación:").grid(row=0, column=2, sticky="w", padx=4, pady=2)
        self.node_eval_entry = tk.Entry(self.node_frame, width=18)
        self.node_eval_entry.grid(row=0, column=3, sticky="ew", padx=4, pady=2)

        tk.Label(self.node_frame, text="Capturadas:").grid(row=1, column=0, sticky="w", padx=4, pady=2)
        self.node_captured_entry = tk.Entry(self.node_frame, width=28)
        self.node_captured_entry.grid(row=1, column=1, sticky="ew", padx=4, pady=2)

        tk.Label(self.node_frame, text="Turno:").grid(row=1, column=2, sticky="w", padx=4, pady=2)
        self.node_side_var = tk.StringVar(value="")
        tk.Label(self.node_frame, textvariable=self.node_side_var, anchor="w").grid(row=1, column=3, sticky="ew", padx=4, pady=2)

        tk.Label(self.node_frame, text="FEN:").grid(row=2, column=0, sticky="nw", padx=4, pady=2)
        self.node_fen = tk.Text(self.node_frame, width=68, height=3, wrap=tk.WORD)
        self.node_fen.grid(row=2, column=1, columnspan=3, sticky="ew", padx=4, pady=2)
        self.node_fen.config(state="disabled")

        node_buttons = tk.Frame(self.node_frame)
        node_buttons.grid(row=3, column=0, columnspan=4, sticky="ew", padx=4, pady=4)
        tk.Button(node_buttons, text="Guardar nodo", command=self.save_selected_node).grid(row=0, column=0, padx=2, pady=2)
        tk.Button(node_buttons, text="Cargar nodo al tablero", command=self.load_selected_node_to_board).grid(row=0, column=1, padx=2, pady=2)
        tk.Button(node_buttons, text="Subir al padre", command=self.open_parent_node).grid(row=0, column=2, padx=2, pady=2)
        tk.Button(node_buttons, text="Primer hijo", command=self.open_first_child).grid(row=0, column=3, padx=2, pady=2)
        tk.Button(node_buttons, text="Eliminar selección", command=self.delete_selected_view_subtree).grid(row=0, column=4, padx=2, pady=2)

        child_form = tk.LabelFrame(self.main_frame, text="Agregar continuación desde el nodo seleccionado")
        child_form.grid(row=3, column=0, sticky="ew", padx=4, pady=4)
        child_form.columnconfigure(1, weight=1)
        child_form.columnconfigure(3, weight=1)
        child_form.columnconfigure(5, weight=1)

        tk.Label(child_form, text="Jugada:").grid(row=0, column=0, sticky="w", padx=2, pady=2)
        self.move_entry = tk.Entry(child_form, width=12)
        self.move_entry.grid(row=0, column=1, sticky="ew", padx=2, pady=2)
        tk.Label(child_form, text="Nombre:").grid(row=0, column=2, sticky="w", padx=2, pady=2)
        self.child_name_entry = tk.Entry(child_form, width=24)
        self.child_name_entry.grid(row=0, column=3, sticky="ew", padx=2, pady=2)
        tk.Label(child_form, text="Evaluación:").grid(row=0, column=4, sticky="w", padx=2, pady=2)
        self.child_eval_entry = tk.Entry(child_form, width=14)
        self.child_eval_entry.grid(row=0, column=5, sticky="ew", padx=2, pady=2)
        tk.Button(child_form, text="Agregar", command=self.add_child_from_move).grid(row=0, column=6, padx=2, pady=2)

        self.view_frame = tk.LabelFrame(self.main_frame, text="Vista local")
        self.view_frame.grid(row=4, column=0, sticky="nsew", padx=4, pady=4)
        self.view_frame.rowconfigure(0, weight=1)
        self.view_frame.columnconfigure(0, weight=1)

        self.local_view = ttk.Treeview(
            self.view_frame,
            columns=("move", "name", "side", "evaluation"),
            show="tree headings",
            selectmode="browse",
            height=10,
        )
        self.local_view.heading("#0", text="Rol")
        self.local_view.heading("move", text="Jugada")
        self.local_view.heading("name", text="Nombre")
        self.local_view.heading("side", text="Turno")
        self.local_view.heading("evaluation", text="Evaluación")
        self.local_view.column("#0", width=120, stretch=False)
        self.local_view.column("move", width=90, stretch=False)
        self.local_view.column("name", width=260, stretch=True)
        self.local_view.column("side", width=70, stretch=False)
        self.local_view.column("evaluation", width=100, stretch=False)
        self.local_view.grid(row=0, column=0, sticky="nsew")
        self.local_view.bind("<Double-Button-1>", self._on_local_view_double_click)

        scrollbar = ttk.Scrollbar(self.view_frame, orient="vertical", command=self.local_view.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.local_view.configure(yscrollcommand=scrollbar.set)

        hint = "Teclado: ↑ padre · ↓ primer hijo · ←/→ hermanos · Enter abrir selección"
        tk.Label(self.main_frame, text=hint, anchor="w").grid(row=5, column=0, sticky="ew", padx=4, pady=(0, 2))

    def _bind_keys(self) -> None:
        self.window.bind("<Up>", lambda event: self._navigate_parent())
        self.window.bind("<Down>", lambda event: self._navigate_first_child())
        self.window.bind("<Left>", lambda event: self._navigate_sibling(-1))
        self.window.bind("<Right>", lambda event: self._navigate_sibling(1))
        self.window.bind("<Return>", lambda event: self._open_selected_view_item())

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
        view = self.controller.get_local_view()
        self.source_var.set(self.controller.selected_book_source_label())
        self._set_path_text(view)
        self._set_node_fields(view.current_node)
        self._refresh_local_view(view)

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

    def rename_selected_book(self) -> None:
        book_id = self._selected_book_id_from_list_or_controller()
        if book_id is None:
            return
        book = self.controller.service.get_book(book_id)
        current_name = book.name if book is not None else ""
        name = simpledialog.askstring("Renombrar entrada", "Nuevo nombre:", initialvalue=current_name, parent=self.window)
        if name is None:
            return
        try:
            self.controller.update_book(book_id, name=name)
        except Exception as exc:
            messagebox.showerror("No se pudo renombrar la entrada", str(exc), parent=self.window)
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

    def save_selected_node(self) -> None:
        if self.controller.selected_node_id is None:
            return
        try:
            self.controller.update_selected_node(
                name=self.node_name_entry.get(),
                evaluation=self.node_eval_entry.get(),
                captured_pieces=self.node_captured_entry.get(),
            )
        except Exception as exc:
            messagebox.showerror("No se pudo guardar el nodo", str(exc), parent=self.window)
            return
        self.refresh_all()

    def add_child_from_move(self) -> None:
        node = self.controller.get_selected_node()
        if node is None:
            messagebox.showwarning("Sin nodo", "Selecciona un nodo padre primero.", parent=self.window)
            return

        move_san = self.move_entry.get().strip()
        name = self.child_name_entry.get().strip() or None
        evaluation = self.child_eval_entry.get().strip() or None
        if not move_san:
            messagebox.showwarning("Jugada requerida", "La relación necesita una jugada.", parent=self.window)
            return

        try:
            branch = self.controller.add_child_by_move(
                node.id,
                move_san=move_san,
                name=name,
                evaluation=evaluation,
            )
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
        self.child_eval_entry.delete(0, tk.END)
        if self.on_board_changed is not None:
            self.on_board_changed()
        self.refresh_all()

    def open_parent_node(self) -> None:
        branch = self.controller.get_parent_branch()
        if branch is None:
            return
        self.controller.select_node(branch.node.id)
        self.refresh_node_panel()

    def open_first_child(self) -> None:
        if self.controller.select_first_child() is None:
            return
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

    def delete_selected_view_subtree(self) -> None:
        node_id = self._selected_view_node_id() or self.controller.selected_node_id
        if node_id is None:
            return
        self._delete_subtree(node_id)

    def _delete_subtree(self, node_id: str) -> None:
        parent_before_delete = self.controller.get_parent_branch(node_id)
        preview = self.controller.preview_delete_subtree(node_id)
        labels = "\n".join(f"- {label}" for label in preview.labels[:12])
        if len(preview.labels) > 12:
            labels += f"\n- ... y {len(preview.labels) - 12} más"
        message = (
            f"Se borrarán {preview.node_count} nodo(s) y {preview.edge_count} relación(es).\n\n"
            f"{labels}\n\n¿Continuar?"
        )
        if not messagebox.askyesno("Borrar rama", message, parent=self.window):
            return
        self.controller.delete_subtree(node_id)
        if parent_before_delete is not None:
            self.controller.select_node(parent_before_delete.node.id)
        elif self.controller.selected_book_id is not None:
            self.controller.select_book(self.controller.selected_book_id)
        self.refresh_all()

    def _on_book_select(self, event) -> None:
        del event
        book_id = self._selected_book_id_from_list()
        if book_id is None:
            return
        self.controller.select_book(book_id)
        self.refresh_node_panel()

    def _on_local_view_double_click(self, event) -> None:
        del event
        self._open_selected_view_item()

    def _open_selected_view_item(self) -> None:
        selection = self.local_view.selection()
        if not selection:
            return
        action = self.view_item_actions.get(selection[0])
        if action is None:
            return
        action_name, node_id = action
        if action_name == "open":
            self.controller.select_node(node_id)
            self.refresh_node_panel()

    def _navigate_parent(self):
        self.open_parent_node()
        return "break"

    def _navigate_first_child(self):
        self.open_first_child()
        return "break"

    def _navigate_sibling(self, offset: int):
        self.controller.select_sibling(offset)
        self.refresh_node_panel()
        return "break"

    def _set_path_text(self, view: TheoryLocalView) -> None:
        if view.current_node is None:
            self.path_var.set("Ruta: —")
            return
        book_moves = list(view.book.initial_moves) if view.book is not None else []
        path_moves = [branch.edge.move_san for branch in view.path]
        moves = book_moves + path_moves
        self.path_var.set("Ruta: " + (" ".join(moves) if moves else "Raíz"))

    def _set_node_fields(self, node: Optional[TheoryNode]) -> None:
        self._replace_entry_text(self.node_name_entry, node.name if node else "")
        self._replace_entry_text(self.node_eval_entry, node.evaluation if node else "")
        self._replace_entry_text(self.node_captured_entry, node.captured_pieces if node else "")
        self.node_side_var.set(node.side_to_move if node else "")

        self.node_fen.config(state="normal")
        self.node_fen.delete("1.0", tk.END)
        if node is not None:
            self.node_fen.insert(tk.END, node.fen)
        self.node_fen.config(state="disabled")

    def _refresh_local_view(self, view: TheoryLocalView) -> None:
        self.view_item_actions.clear()
        self.local_view.delete(*self.local_view.get_children())

        if view.current_node is None:
            return

        if view.parent_branch is not None:
            parent_item = self.local_view.insert(
                "",
                tk.END,
                text="Padre",
                values=(view.parent_branch.edge.move_san, self._node_label(view.parent_branch.node), view.parent_branch.node.side_to_move, view.parent_branch.node.evaluation or ""),
            )
            self.view_item_actions[parent_item] = ("open", view.parent_branch.node.id)

        current_item = self.local_view.insert(
            "",
            tk.END,
            text="Actual",
            values=("", self._node_label(view.current_node), view.current_node.side_to_move, view.current_node.evaluation or ""),
        )
        self.view_item_actions[current_item] = ("open", view.current_node.id)
        self.local_view.selection_set(current_item)

        if view.siblings:
            for branch in view.siblings:
                if branch.node.id == view.current_node.id:
                    continue
                item = self.local_view.insert(
                    "",
                    tk.END,
                    text="Hermano",
                    values=(branch.edge.move_san, self._node_label(branch.node), branch.node.side_to_move, branch.node.evaluation or ""),
                )
                self.view_item_actions[item] = ("open", branch.node.id)

        for branch in view.children:
            item = self.local_view.insert(
                "",
                tk.END,
                text="Hijo",
                values=(branch.edge.move_san, self._node_label(branch.node), branch.node.side_to_move, branch.node.evaluation or ""),
            )
            self.view_item_actions[item] = ("open", branch.node.id)

    def _selected_book_id_from_list(self) -> Optional[str]:
        selection = self.book_list.curselection()
        if not selection:
            return None
        return self.book_index.get(selection[0])

    def _selected_book_id_from_list_or_controller(self) -> Optional[str]:
        return self._selected_book_id_from_list() or self.controller.selected_book_id

    def _selected_view_node_id(self) -> Optional[str]:
        selection = self.local_view.selection()
        if not selection:
            return None
        action = self.view_item_actions.get(selection[0])
        if action is None:
            return None
        return action[1]

    @staticmethod
    def _replace_entry_text(entry: tk.Entry, value: Optional[str]) -> None:
        entry.delete(0, tk.END)
        if value:
            entry.insert(0, value)

    @staticmethod
    def _node_label(node: TheoryNode) -> str:
        return node.name or node.fen.split()[0][:36]
