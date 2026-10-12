#!/usr/bin/env python3
"""A simple desktop calculator."""

import tkinter as tk
from decimal import Decimal, DivisionByZero, InvalidOperation

OPERATORS = {
    "+": lambda a, b: a + b,
    "-": lambda a, b: a - b,
    "x": lambda a, b: a * b,
    "/": lambda a, b: a / b,
}


class Calculator(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Calculator")
        self.resizable(False, False)
        self.configure(bg="#1c1c1c")

        self.entry = ""          # digits typed so far
        self.accumulator = None  # left-hand value
        self.pending = None      # pending operator symbol
        self.fresh = True        # display shows a result, not user input

        self.display = tk.Label(
            self, text="0", anchor="e", bg="#1c1c1c", fg="white",
            font=("Helvetica", 36), padx=12, pady=16,
        )
        self.display.grid(row=0, column=0, columnspan=4, sticky="we")

        layout = [
            ("C", "±", "%", "/"),
            ("7", "8", "9", "x"),
            ("4", "5", "6", "-"),
            ("1", "2", "3", "+"),
            ("0", ".", "="),
        ]
        for r, row in enumerate(layout, start=1):
            for c, label in enumerate(row):
                span = 2 if label == "0" else 1
                col = c + 1 if r == 5 and c > 0 else c
                tk.Button(
                    self, text=label, font=("Helvetica", 20), width=4, height=1,
                    bd=0, highlightthickness=0,
                    bg="#ff9f0a" if label in OPERATORS or label == "=" else "#333333",
                    fg="white", activebackground="#555555", activeforeground="white",
                    command=lambda l=label: self.press(l),
                ).grid(row=r, column=col, columnspan=span, sticky="nsew", padx=1, pady=1)

        for key in "0123456789":
            self.bind(key, lambda e: self.press(e.char))
        self.bind(".", lambda e: self.press("."))
        self.bind("+", lambda e: self.press("+"))
        self.bind("-", lambda e: self.press("-"))
        self.bind("*", lambda e: self.press("x"))
        self.bind("/", lambda e: self.press("/"))
        self.bind("<Return>", lambda e: self.press("="))
        self.bind("<BackSpace>", lambda e: self.backspace())
        self.bind("<Escape>", lambda e: self.press("C"))

    def show(self, text):
        self.display.config(text=text)

    def current(self):
        return Decimal(self.entry) if self.entry else Decimal(0)

    @staticmethod
    def format(value):
        value = value.normalize()
        sign, digits, exp = value.as_tuple()
        if exp > 0:  # avoid 1E+3 for integers
            value = value.quantize(Decimal(1))
        text = f"{value:f}"
        return text[:16]

    def press(self, label):
        if label == "C":
            self.reset()
        elif label.isdigit():
            self.digit(label)
        elif label == ".":
            self.decimal_point()
        elif label == "±":
            self.negate()
        elif label == "%":
            self.percent()
        elif label in OPERATORS:
            self.operator(label)
        elif label == "=":
            self.equals()

    def reset(self):
        self.entry = ""
        self.accumulator = None
        self.pending = None
        self.fresh = True
        self.show("0")

    def digit(self, d):
        if self.fresh:
            self.entry = ""
            self.fresh = False
        if len(self.entry.lstrip("-0.")) >= 15:
            return
        self.entry = d if self.entry in ("", "0") else self.entry + d
        self.show(self.entry)

    def decimal_point(self):
        if self.fresh:
            self.entry = "0"
            self.fresh = False
        if "." not in self.entry:
            self.entry = (self.entry or "0") + "."
            self.show(self.entry)

    def negate(self):
        if self.entry.startswith("-"):
            self.entry = self.entry[1:]
        elif self.entry not in ("", "0"):
            self.entry = "-" + self.entry
        else:
            return
        self.show(self.entry)

    def percent(self):
        try:
            self.entry = self.format(self.current() / 100)
        except (InvalidOperation, DivisionByZero):
            return
        self.fresh = False
        self.show(self.entry)

    def backspace(self):
        if self.fresh or not self.entry:
            return
        self.entry = self.entry[:-1]
        self.show(self.entry or "0")

    def operator(self, symbol):
        if self.pending and not self.fresh:
            if not self.compute():
                return
        elif self.accumulator is None or not self.fresh:
            self.accumulator = self.current()
        self.pending = symbol
        self.fresh = True

    def equals(self):
        if self.pending and self.compute():
            self.pending = None

    def compute(self):
        try:
            result = OPERATORS[self.pending](self.accumulator, self.current())
        except (DivisionByZero, InvalidOperation):
            self.show("Error")
            self.entry = ""
            self.accumulator = None
            self.pending = None
            self.fresh = True
            return False
        self.accumulator = result
        self.entry = self.format(result)
        self.fresh = True
        self.show(self.entry)
        return True


if __name__ == "__main__":
    Calculator().mainloop()
