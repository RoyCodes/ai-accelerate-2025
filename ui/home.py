import mesop as me

# Page State:

@me.stateclass
class State:
   input: str = "awaiting click..."

# Page Functions:


# Page Rendering:

# Global Style:
ROOT_BOX_STYLE = me.Style(
    background="#e7f2ff",
    height="100%",
    font_family="Inter",
    display="flex",
    flex_direction="column",
)

# Page Components:
def header():
   with me.box(
      style=me.Style(
         padding=me.Padding.all(16),
      ),
   ):
    me.text("Hello, World!")

def button():
   me.button(
      label="Click Me", 
      color="primary", 
      type="flat",
      )

# Page Path and Tree:
@me.page(
    path="/",
    stylesheets=[
        "https://fonts.googleapis.com/css2?family=Inter:wght@100..900&display=swap"
    ],
)
def page():
    with me.box(style=ROOT_BOX_STYLE):
        header()
        with me.box(style=me.Style(
            background="grey",
            width="min(800px, 100%)",
            margin=me.Margin.symmetric(
                horizontal="auto",
                vertical=36,
                ),
            padding=me.Padding.all(16)
        )):
            me.text("Hello from ai-accelerate-2025!")
            button()
            with me.box(
               style=me.Style(
                  display="flex",
                  flex_direction="row",
                  gap=16,
                  margin=me.Margin.all(15),
                  max_width=500
               )
            ):
                with me.card(appearance='raised'):
                    me.card_header(
                        title="Machines",
                        subtitle="Current machines on site.",
                )