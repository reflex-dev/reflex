# Your First Reflex Build App

In this tutorial, you'll build a data dashboard application that displays employee information in both table and chart formats, with interactive features for filtering and adding new data. We'll also add a simple chatbot page to demonstrate multi-page navigation.

## What You'll Build

By the end of this tutorial, you'll have created:
- A dashboard displaying employee data in a table and bar chart
- Interactive filtering to search through your data
- A modal form for adding new employees
- A separate page with a simple chatbot interface

This tutorial assumes you're starting with a new project in AI Builder.

---

## Creating Your Dashboard

Let's start by building the core of our application - a dashboard that displays employee data.

**Prompt:**
```
Create a dashboard page with a table showing sample employee data with columns: Name, Department, and Salary. Below the table, add a bar chart that visualizes the salary data. Include at least 5 sample employees with different departments and salary ranges.
```

This will create your main dashboard page with both tabular and visual representations of your data. The AI will generate sample employee records and create a bar chart that makes it easy to compare salaries across your team.

```python exec
import reflex as rx
```

```python eval
rx.el.div(
    rx.image(
        src="https://web.reflex-assets.dev/ai_builder/overview/tutorial_1_light.avif",
        class_name="rounded-md h-auto",
        border=f"0.81px solid {rx.color('slate', 5)}",
    ),
    class_name="w-full flex flex-col rounded-md",
)
```

## Adding Interactive Filtering

Now that you have your basic dashboard, let's make it more interactive by adding the ability to filter and search through your employee data.

**Prompt:**
```
Add filtering functionality to the employee table. Include a search input above the table that filters rows based on name, and dropdown filters for department. Make sure the filters work together and update the table in real-time.
```

Your dashboard now becomes much more useful with real-time filtering. Users can quickly find specific employees by name or narrow down results by department. The filters work together, so you can combine a department filter with a name search.

```python eval
rx.el.div(
    rx.image(
        src="https://web.reflex-assets.dev/ai_builder/overview/tutorial_2_light.avif",
        class_name="rounded-md h-auto",
        border=f"0.81px solid {rx.color('slate', 5)}",
    ),
    class_name="w-full flex flex-col rounded-md",
)
```


## Enabling Data Entry

A static dashboard is useful, but being able to add new data makes your app much more practical. Let's add the ability to create new employee records.

**Prompt:**
```
Add an "Add Employee" button above the table. When clicked, open a modal with input fields for Name, Department, and Salary. When the form is submitted, add the new employee to the table and update the bar chart. Include form validation for required fields.
```

Your app now has full CRUD capability for employee records. The modal form provides a clean interface for data entry, and both your table and chart update immediately when new employees are added.


```python eval
rx.el.div(
    rx.image(
        src="https://web.reflex-assets.dev/ai_builder/overview/tutorial_3_light.avif",
        class_name="rounded-md h-auto",
        border=f"0.81px solid {rx.color('slate', 5)}",
    ),
    class_name="w-full flex flex-col rounded-md",
)
```


## Building a Multi-Page App

Most real applications have multiple pages. Let's add a chatbot page to demonstrate navigation and create a more complete user experience.

**Prompt:**
```
Create a new page called "Chat" and add it to the navigation. Build a simple chatbot interface with a message input field, send button, and chat history display. For now, make the bot echo back the user's messages with "Bot says: [user message]".
```

Your app now has proper navigation between the dashboard and chat functionality. The chatbot page demonstrates how easy it is to add new features and pages to your AI Builder application.


```python eval
rx.el.div(
    rx.image(
        src="https://web.reflex-assets.dev/ai_builder/overview/tutorial_4_light.avif",
        class_name="rounded-md h-auto",
        border=f"0.81px solid {rx.color('slate', 5)}",
    ),
    class_name="w-full flex flex-col rounded-md",
)
```

## What's Next?

You've successfully built a complete web application with data visualization, interactive filtering, data entry, and multi-page navigation. Your app demonstrates many common patterns used in modern web applications:

- **Data presentation** with tables and charts
- **User interaction** through filtering and forms
- **Real-time updates** when data changes
- **Multi-page architecture** with navigation

## Exploring Further

Now that you have a working foundation, try experimenting with these ideas:

- **Customize the data model** - change the employee fields or add new columns
- **Enhance the visualizations** - try different chart types or add more charts
- **Improve the chatbot** - give it more sophisticated responses or integrate it with your employee data
- **Add more pages** - create additional features like employee profiles or reporting dashboards

The power of AI Builder is that you can iterate quickly with natural language prompts. Each new feature is just a conversation away!
