import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.edge.service import Service
from bs4 import BeautifulSoup
import pyperclip
import glob
import os
import threading
import time

def find_edge_driver_locally():
    """Search common locations where msedgedriver.exe may already exist."""
    candidates = []

    # Known local copy
    candidates.append(r"C:\Users\Admin\Downloads\edgedriver_win64 (1)\msedgedriver.exe")

    # Edge application folders (versioned sub-directories)
    for base in [
        r"C:\Program Files (x86)\Microsoft\Edge\Application",
        r"C:\Program Files\Microsoft\Edge\Application",
    ]:
        candidates += glob.glob(os.path.join(base, "*", "msedgedriver.exe"))
        candidates.append(os.path.join(base, "msedgedriver.exe"))

    # Anywhere on PATH
    for folder in os.environ.get("PATH", "").split(os.pathsep):
        candidates.append(os.path.join(folder, "msedgedriver.exe"))

    for path in candidates:
        if os.path.isfile(path):
            return path
    return None

def create_driver(driver_path=""):
    options = webdriver.EdgeOptions()
    options.add_argument('--headless')

    # 1. User-supplied path
    if driver_path and os.path.isfile(driver_path):
        return webdriver.Edge(service=Service(driver_path), options=options)

    # 2. Auto-detect from Edge installation or PATH
    found = find_edge_driver_locally()
    if found:
        return webdriver.Edge(service=Service(found), options=options)

    # 3. Try webdriver-manager (requires internet)
    try:
        from webdriver_manager.microsoft import EdgeChromiumDriverManager
        return webdriver.Edge(service=Service(EdgeChromiumDriverManager().install()), options=options)
    except Exception:
        pass

    raise RuntimeError(
        "msedgedriver.exe not found.\n\n"
        "Download the driver that matches your Edge version from:\n"
        "https://developer.microsoft.com/en-us/microsoft-edge/tools/webdriver/\n\n"
        "Then paste the path into the 'Edge Driver Path' field and try again."
    )

# === LOCATOR DETECTION FUNCTION ===
def get_element_locator_after_login(login_url, target_url, username, password, search_text, search_by, locator_type, driver_path=""):
    try:
        driver = create_driver(driver_path)

        do_login = login_url and username and password

        if do_login:
            # 1. Go to login page
            driver.get(login_url)

            # 2. Attempt to find login fields
            user_input = driver.find_element(By.XPATH, "//input[@type='text' or @name='username' or contains(@placeholder, 'User')]")
            pass_input = driver.find_element(By.XPATH, "//input[@type='password']")

            user_input.send_keys(username)
            pass_input.send_keys(password)
            pass_input.send_keys(Keys.RETURN)

            time.sleep(2)  # Wait for login to complete

        # 3. Go to target page
        driver.get(target_url)
        time.sleep(3)

        html = driver.page_source
        soup = BeautifulSoup(html, "html.parser")
        driver.quit()

        # 4. Find element based on the chosen search_by mode.
        query = search_text.lower()
        best = None
        best_depth = -1

        def depth(tag):
            return sum(1 for _ in tag.parents)

        ALL_ATTRS = ("value", "aria-label", "placeholder", "title", "alt", "name", "role", "type", "id", "class")

        for tag in soup.find_all(True):
            tag_depth = depth(tag)
            matched = False

            if search_by == "Text":
                visible = tag.get_text(separator=" ", strip=True).lower()
                matched = query in visible
            elif search_by == "Any":
                visible = tag.get_text(separator=" ", strip=True).lower()
                if query in visible:
                    matched = True
                else:
                    for attr in ALL_ATTRS:
                        val = tag.attrs.get(attr, "")
                        if isinstance(val, list):
                            val = " ".join(val)
                        if query in val.lower():
                            matched = True
                            break
            else:
                # Specific attribute search (value, name, type, role, id, class, etc.)
                attr_key = search_by.lower().replace("-", "").replace(" ", "-")
                # normalise "aria-label" label
                attr_map = {
                    "arialabel": "aria-label",
                    "aria-label": "aria-label",
                    "class": "class",
                    "id": "id",
                }
                attr_key = attr_map.get(attr_key, attr_key)
                val = tag.attrs.get(attr_key, "")
                if isinstance(val, list):
                    val = " ".join(val)
                matched = query in val.lower()

            if matched and tag_depth > best_depth:
                best = tag
                best_depth = tag_depth

        if not best:
            return "Element not found."

        target = best

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
        elif locator_type == "Value":
            return attrs.get("value", "No value attribute.")
        elif locator_type == "Type":
            return attrs.get("type", "No type attribute.")
        elif locator_type == "Role":
            return attrs.get("role", "No role attribute.")
        else:
            return "Unsupported locator type."

    except Exception as e:
        return f"Error: {str(e)}"

# === VALIDATION / HIGHLIGHT STATE ===
_live_driver = None  # non-headless browser kept open for highlight

def _get_inputs():
    return {
        "login_url":   entry_login_url.get().strip(),
        "target_url":  entry_target_url.get().strip(),
        "username":    entry_username.get().strip(),
        "password":    entry_password.get().strip(),
        "driver_path": entry_driver_path.get().strip(),
        "locator_type": combo_locator.get(),
    }

def _locator_value_from_output():
    """Extract the raw locator string from the last generated code in the output box."""
    raw = text_output.get("1.0", tk.END).strip()
    # Selenium: driver.find_element(By.XPATH, '...')
    import re
    m = re.search(r"find_element\([^,]+,\s*'([^']+)'\)", raw)
    if m:
        return m.group(1)
    # cy.get / cy.xpath / plain locator
    m = re.search(r"(?:cy\.xpath|cy\.get)\('([^']+)'\)", raw)
    if m:
        return m.group(1)
    # Katalon or raw value — return as-is
    return raw

SELENIUM_BY_MAP = {
    "XPath":             By.XPATH,
    "CSS Selector":      By.CSS_SELECTOR,
    "ID":                By.ID,
    "Class":             By.CLASS_NAME,
    "Name":              By.NAME,
    "Tag":               By.TAG_NAME,
    "Link Text":         By.LINK_TEXT,
    "Partial Link Text": By.PARTIAL_LINK_TEXT,
}

def _by_and_locator(locator_type, locator_value):
    """Return (By.*, locator_string) — attribute types are wrapped in XPath."""
    if locator_type in SELENIUM_BY_MAP:
        return SELENIUM_BY_MAP[locator_type], locator_value
    # Attribute-only types: build XPath
    attr_map = {
        "Aria-label": "aria-label",
        "Title":      "title",
        "Value":      "value",
        "Type":       "type",
        "Role":       "role",
    }
    attr = attr_map.get(locator_type, locator_type.lower())
    return By.XPATH, f"//*[@{attr}='{locator_value}']"

def _navigate_to_target(driver, inp):
    if inp["login_url"] and inp["username"] and inp["password"]:
        driver.get(inp["login_url"])
        time.sleep(2)
        try:
            u = driver.find_element(By.XPATH, "//input[@type='text' or @name='username' or contains(@placeholder,'User')]")
            p = driver.find_element(By.XPATH, "//input[@type='password']")
            u.send_keys(inp["username"])
            p.send_keys(inp["password"])
            p.send_keys(Keys.RETURN)
            time.sleep(2)
        except Exception:
            pass
    driver.get(inp["target_url"])
    time.sleep(3)

def _create_visible_driver(inp):
    """Non-headless driver for highlight."""
    options = webdriver.EdgeOptions()
    dp = inp["driver_path"]
    if dp and os.path.isfile(dp):
        return webdriver.Edge(service=Service(dp), options=options)
    found = find_edge_driver_locally()
    if found:
        return webdriver.Edge(service=Service(found), options=options)
    raise RuntimeError("msedgedriver.exe not found.")

# === VALIDATE LOCATOR ===
def validate_locator():
    locator_value = _locator_value_from_output()
    if not locator_value:
        messagebox.showwarning("No Locator", "Generate a locator first.")
        return
    inp = _get_inputs()
    if not inp["target_url"]:
        messagebox.showwarning("Missing", "Target Page URL is required.")
        return

    btn_validate.config(state="disabled", text="Validating…")
    root.update()

    def run():
        try:
            driver = create_driver(inp["driver_path"])
            _navigate_to_target(driver, inp)
            by, val = _by_and_locator(inp["locator_type"], locator_value)
            elements = driver.find_elements(by, val)
            count = len(elements)
            driver.quit()
            if count == 1:
                msg = f"✅ Valid — exactly 1 element found."
                color = "#d4edda"
            elif count == 0:
                msg = f"❌ No element found with this locator."
                color = "#f8d7da"
            else:
                msg = f"⚠️ {count} elements matched — locator is not unique."
                color = "#fff3cd"
            root.after(0, lambda: _show_validation_result(msg, color))
        except Exception as e:
            root.after(0, lambda: _show_validation_result(f"Error: {e}", "#f8d7da"))
        finally:
            root.after(0, lambda: btn_validate.config(state="normal", text="✔ Validate Locator"))

    threading.Thread(target=run, daemon=True).start()

def _show_validation_result(msg, color):
    text_output.config(bg=color)
    text_output.delete(1.0, tk.END)
    text_output.insert(tk.END, msg)
    root.after(3000, lambda: text_output.config(bg="white"))

# === HIGHLIGHT ELEMENT ===
def highlight_element():
    global _live_driver
    locator_value = _locator_value_from_output()
    if not locator_value:
        messagebox.showwarning("No Locator", "Generate a locator first.")
        return
    inp = _get_inputs()
    if not inp["target_url"]:
        messagebox.showwarning("Missing", "Target Page URL is required.")
        return

    btn_highlight.config(state="disabled", text="Opening browser…")
    root.update()

    def run():
        global _live_driver
        try:
            # Close any previous live browser
            if _live_driver:
                try:
                    _live_driver.quit()
                except Exception:
                    pass
                _live_driver = None

            driver = _create_visible_driver(inp)
            _navigate_to_target(driver, inp)
            by, val = _by_and_locator(inp["locator_type"], locator_value)
            elements = driver.find_elements(by, val)

            if not elements:
                driver.quit()
                root.after(0, lambda: messagebox.showerror("Not Found", "No element found with this locator."))
                return

            # Highlight all matches: red border + yellow background
            for el in elements:
                driver.execute_script(
                    "arguments[0].style.outline='3px solid red';"
                    "arguments[0].style.backgroundColor='yellow';"
                    "arguments[0].scrollIntoView({block:'center'});",
                    el
                )

            _live_driver = driver
            count = len(elements)
            root.after(0, lambda: _on_highlight_done(count))
        except Exception as e:
            root.after(0, lambda: messagebox.showerror("Error", str(e)))
            root.after(0, lambda: btn_highlight.config(state="normal", text="🔦 Highlight Element"))

    threading.Thread(target=run, daemon=True).start()

def _on_highlight_done(count):
    btn_highlight.config(state="normal", text="🔦 Highlight Element")
    btn_close_browser.config(state="normal")
    text_output.delete(1.0, tk.END)
    text_output.insert(tk.END,
        f"✅ {count} element(s) highlighted in the browser.\n"
        "Close the browser window manually or click 'Close Browser'."
    )

def close_browser():
    global _live_driver
    if _live_driver:
        try:
            _live_driver.quit()
        except Exception:
            pass
        _live_driver = None
    btn_close_browser.config(state="disabled")

# === GENERATE CODE FUNCTION ===
def generate_code():
    login_url = entry_login_url.get()
    target_url = entry_target_url.get()
    username = entry_username.get()
    password = entry_password.get()
    text = entry_text.get()
    search_by = combo_search_by.get()
    tool = combo_tool.get()
    locator_type = combo_locator.get()
    driver_path = entry_driver_path.get().strip()

    if not target_url or not text:
        messagebox.showwarning("Missing", "Target Page URL and search value are required.")
        return

    locator = get_element_locator_after_login(login_url, target_url, username, password, text, search_by, locator_type, driver_path)

    if "Error" in locator or "not found" in locator:
        text_output.delete(1.0, tk.END)
        text_output.insert(tk.END, locator)
        return

    if tool == "Selenium":
        code = f"driver.find_element(By.{locator_type.upper().replace(' ', '_')}, '{locator}')"
    elif tool == "Cypress":
        code = f"cy.xpath('{locator}')" if locator_type == "XPath" else f"cy.get('{locator}')"
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
root.title("🔐 Locator After Login Tool")
root.geometry("740x560")

# Input fields
tk.Label(root, text="🔑 Login Page URL:").pack()
entry_login_url = tk.Entry(root, width=90)
entry_login_url.pack(pady=2)

tk.Label(root, text="👤 Username:").pack()
entry_username = tk.Entry(root, width=90)
entry_username.pack(pady=2)

tk.Label(root, text="🔒 Password:").pack()
entry_password = tk.Entry(root, show='*', width=90)
entry_password.pack(pady=2)

tk.Label(root, text="🎯 Target Page URL:").pack()
entry_target_url = tk.Entry(root, width=90)
entry_target_url.pack(pady=2)

tk.Label(root, text="🔍 Search Element:").pack()
frame_search = tk.Frame(root)
frame_search.pack(pady=2)
search_by_options = ["Any", "Text", "Value", "Name", "Type", "Role",
                     "Aria-label", "Placeholder", "ID", "Class", "Title", "Alt"]
combo_search_by = ttk.Combobox(frame_search, values=search_by_options, width=12, state="readonly")
combo_search_by.set("Any")
combo_search_by.pack(side="left", padx=(0, 4))
entry_text = tk.Entry(frame_search, width=72)
entry_text.pack(side="left")

tk.Label(root, text="⚙️ Edge Driver Path (optional, for offline use):").pack()
frame_driver = tk.Frame(root)
frame_driver.pack(pady=2)
entry_driver_path = tk.Entry(frame_driver, width=78)
entry_driver_path.insert(0, r"C:\Users\Admin\Downloads\edgedriver_win64 (1)\msedgedriver.exe")
entry_driver_path.pack(side="left")
tk.Button(frame_driver, text="Browse",
          command=lambda: (entry_driver_path.delete(0, tk.END),
                           entry_driver_path.insert(0, filedialog.askopenfilename(
                               title="Select msedgedriver.exe",
                               filetypes=[("Edge Driver", "msedgedriver.exe"), ("All files", "*.*")]
                           )))).pack(side="left", padx=4)

# Options frame
frame_opts = tk.Frame(root)
frame_opts.pack(pady=6)

locator_types = ["XPath", "CSS Selector", "ID", "Class", "Name", "Tag", "Link Text",
                 "Partial Link Text", "Aria-label", "Title", "Value", "Type", "Role"]
combo_locator = ttk.Combobox(frame_opts, values=locator_types, width=20)
combo_locator.set("XPath")
combo_locator.grid(row=0, column=0, padx=5)

combo_tool = ttk.Combobox(frame_opts, values=["Selenium", "Cypress", "Katalon"], width=20)
combo_tool.set("Selenium")
combo_tool.grid(row=0, column=1, padx=5)

# Buttons — row 1: generate + copy
frame_btns = tk.Frame(root)
frame_btns.pack(pady=(8, 2))

tk.Button(frame_btns, text="🚀 Generate Locator Code", command=generate_code).grid(row=0, column=0, padx=8)
tk.Button(frame_btns, text="📋 Copy to Clipboard",     command=copy_to_clipboard).grid(row=0, column=1, padx=8)

# Buttons — row 2: validate + highlight + close browser
frame_btns2 = tk.Frame(root)
frame_btns2.pack(pady=(2, 6))

btn_validate = tk.Button(frame_btns2, text="✔ Validate Locator",  command=validate_locator,  width=20)
btn_validate.grid(row=0, column=0, padx=8)

btn_highlight = tk.Button(frame_btns2, text="🔦 Highlight Element", command=highlight_element, width=20)
btn_highlight.grid(row=0, column=1, padx=8)

btn_close_browser = tk.Button(frame_btns2, text="✖ Close Browser", command=close_browser, width=16, state="disabled")
btn_close_browser.grid(row=0, column=2, padx=8)

# Output box
text_output = tk.Text(root, height=12, wrap="word")
text_output.pack(pady=10, fill="both", expand=True)

root.mainloop()
