import tkinter as tk
from tkinter import ttk, messagebox
from selenium import webdriver
from selenium.webdriver.edge.service import Service
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup
import pyperclip

# === CONFIG ===
EDGE_DRIVER_PATH = r"C:\\Users\\Admin\\Downloads\\edgedriver_win64\\msedgedriver.exe"

# === LOCATOR DETECTION FUNCTION ===
def get_element_locator(url, search_text, locator_type):
    try:
        service = Service(executable_path=EDGE_DRIVER_PATH)
        options = webdriver.EdgeOptions()
        options.add_argument('--headless')
        driver = webdriver.Edge(service=service, options=options)
        driver.get(url)
        html = driver.page_source
        driver.quit()

        soup = BeautifulSoup(html, "html.parser")
        target = None
        for tag in soup.find_all(True):
            if tag.string and search_text.lower() in tag.string.lower():
                target = tag
                break

        if not target:
            return "Element not found."

        attrs = target.attrs

        if locator_type == "XPath":
            attr_filter = ' and '.join([f"@{k}='{v}'" for k, v in attrs.items() if isinstance(v, str)])
            return f"//{target.name}[{attr_filter}]" if attr_filter else f"//{target.name}"

        elif locator_type == "CSS Selector":
            if 'id' in attrs:
                return f"#{attrs['id']}"
            elif 'class' in attrs:
                return f"{target.name}." + ".".join(attrs['class'])
            elif 'name' in attrs:
                return f"{target.name}[name='{attrs['name']}']"
            else:
                return f"{target.name}"

        elif locator_type == "ID":
            return attrs.get('id', "No ID found.")
        elif locator_type == "Class":
            return " ".join(attrs.get('class', ["No class found."]))
        elif locator_type == "Name":
            return attrs.get("name", "No name attribute.")
        elif locator_type == "Tag":
            return target.name
        elif locator_type == "Link Text":
            return target.get_text(strip=True)
        elif locator_type == "Partial Link Text":
            return target.get_text(strip=True)[:5]
        elif locator_type == "Aria-label":
            return attrs.get("aria-label", "No aria-label.")
        elif locator_type == "Title":
            return attrs.get("title", "No title.")
        elif locator_type.startswith("Data-"):
            key = locator_type.split("-")[1]
            return attrs.get(f"data-{key}", f"No data-{key} found.")
        else:
            return "Unsupported locator type."

    except Exception as e:
        return f"Error: {str(e)}"

# === ANALYZE PAGE FUNCTION ===
def analyze_page():
    url = entry_url.get()
    if not url:
        messagebox.showwarning("Missing", "Please enter a URL to analyze.")
        return

    try:
        service = Service(executable_path=EDGE_DRIVER_PATH)
        options = webdriver.EdgeOptions()
        options.add_argument('--headless')
        driver = webdriver.Edge(service=service, options=options)
        driver.get(url)
        html = driver.page_source
        driver.quit()

        soup = BeautifulSoup(html, "html.parser")
        buttons_and_links = []
        for tag in soup.find_all(['button', 'a']):
            text = tag.get_text(strip=True)
            if text:
                buttons_and_links.append(text)

        if not buttons_and_links:
            messagebox.showinfo("No Elements", "No buttons or links found.")
            return

        popup = tk.Toplevel(root)
        popup.title("Select Element Text")
        tk.Label(popup, text="Select an element:").pack(pady=5)
        combo = ttk.Combobox(popup, values=buttons_and_links, width=60)
        combo.pack(pady=5)

        def set_text():
            entry_text.delete(0, tk.END)
            entry_text.insert(0, combo.get())
            popup.destroy()

        tk.Button(popup, text="Select", command=set_text).pack(pady=5)

    except Exception as e:
        messagebox.showerror("Error", f"Error analyzing page: {e}")

# === GENERATE CODE FUNCTION ===
def generate_code():
    url = entry_url.get()
    text = entry_text.get()
    tool = combo_tool.get()
    locator_type = combo_locator.get()

    if not url or not text:
        messagebox.showwarning("Missing", "Please enter both URL and text.")
        return

    locator = get_element_locator(url, text, locator_type)

    if "Error" in locator or "not found" in locator:
        text_output.delete(1.0, tk.END)
        text_output.insert(tk.END, locator)
        return

    if tool == "Selenium":
        code = f"driver.find_element(By.{locator_type.upper().replace(' ', '_')}, '{locator}')"
    elif tool == "Cypress":
        if locator_type == "XPath":
            code = f"cy.xpath('{locator}')"
        else:
            code = f"cy.get('{locator}')"
    elif tool == "Katalon":
        code = f"""TestObject to = new TestObject()
to.addProperty(\"{locator_type.lower()}\", ConditionType.EQUALS, \"{locator}\")
WebUI.verifyElementPresent(to, 10)"""
    else:
        code = locator

    text_output.delete(1.0, tk.END)
    text_output.insert(tk.END, code)

def copy_to_clipboard():
    pyperclip.copy(text_output.get("1.0", tk.END).strip())
    messagebox.showinfo("Copied", "Code copied to clipboard!")

# === UI ===
root = tk.Tk()
root.title("Locator Generator Tool")
root.geometry("750x550")

# URL
tk.Label(root, text="🔗 Page URL:").pack()
entry_url = tk.Entry(root, width=90)
entry_url.pack(pady=2)

# Element Text
tk.Label(root, text="🔍 Element Text to Search:").pack()
entry_text = tk.Entry(root, width=90)
entry_text.pack(pady=2)

# Options
frame_opts = tk.Frame(root)
frame_opts.pack(pady=6)

tk.Label(frame_opts, text="🔧 Locator Type:").grid(row=0, column=0)
locator_types = ["XPath", "CSS Selector", "ID", "Class", "Name", "Tag", "Link Text", "Partial Link Text", "Aria-label", "Title", "Data-custom"]
combo_locator = ttk.Combobox(frame_opts, values=locator_types, width=20)
combo_locator.set("XPath")
combo_locator.grid(row=0, column=1)

tk.Label(frame_opts, text="⚙️ Tool:").grid(row=0, column=2, padx=10)
combo_tool = ttk.Combobox(frame_opts, values=["Selenium", "Cypress", "Katalon"], width=20)
combo_tool.set("Selenium")
combo_tool.grid(row=0, column=3)

# Buttons
frame_btns = tk.Frame(root)
frame_btns.pack(pady=8)
tk.Button(frame_btns, text="🧠 Analyze Page", command=analyze_page).grid(row=0, column=0, padx=10)
tk.Button(frame_btns, text="🎯 Generate Locator Code", command=generate_code).grid(row=0, column=1, padx=10)
tk.Button(frame_btns, text="📋 Copy to Clipboard", command=copy_to_clipboard).grid(row=0, column=2, padx=10)

# Output
text_output = tk.Text(root, height=15, wrap="word")
text_output.pack(pady=10, fill="both", expand=True)

root.mainloop()
