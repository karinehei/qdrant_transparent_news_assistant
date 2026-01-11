# SQLModel Relationship Configuration Issue

## Problem

When defining SQLModel relationships with forward references and generic types (e.g., `List["RetrievalHit"]`), SQLAlchemy's mapper initialization fails with errors like:

```
sqlalchemy.exc.InvalidRequestError: When initializing mapper Mapper[ChatRun(chatrun)], 
expression "relationship("List['RetrievalHit']")" seems to be using a generic class as 
the argument to relationship(); please state the generic argument using an annotation, 
e.g. "hits: Mapped[List['RetrievalHit']] = relationship()"
```

## Root Cause

SQLAlchemy's relationship mapper tries to parse type annotations at class definition time. When using:
- Generic types like `List["RetrievalHit"]`
- Forward references with `Mapped[List["RetrievalHit"]]`
- Inline relationship definitions within class bodies

SQLAlchemy struggles to resolve these annotations correctly, especially when:
1. Classes reference each other (circular dependencies)
2. Generic type parameters are involved
3. Forward references are used

## Attempted Solutions (That Didn't Work)

1. **Using `Mapped` type annotation:**
   ```python
   hits: Mapped[List["RetrievalHit"]] = Relationship(back_populates="run")
   ```
   - Error: SQLAlchemy still couldn't parse the generic type

2. **Using string-only annotation:**
   ```python
   hits: "RetrievalHit" = Relationship(back_populates="run")
   ```
   - Error: SQLAlchemy couldn't infer one-to-many relationship

3. **Using SQLAlchemy's `relationship()` directly:**
   ```python
   hits: List["RetrievalHit"] = Relationship(
       sa_relationship=sa_relationship("RetrievalHit", back_populates="run")
   )
   ```
   - Error: Forward reference resolution issues

4. **Removing type annotation entirely:**
   ```python
   hits = Relationship(back_populates="run")
   ```
   - Error: SQLModel requires annotations (`KeyError: 'hits'`)

## Working Solution

**Define relationships after both classes are declared:**

```python
from __future__ import annotations
from typing import Optional, List, Dict, Any
from sqlmodel import SQLModel, Field, Relationship

class ChatRun(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    # ... other fields ...
    # Relationship will be defined after both classes are declared

class RetrievalHit(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="chatrun.id", index=True)
    # ... other fields ...
    # Relationship will be defined after both classes are declared

# Define relationships after both classes are declared
# This avoids forward reference and generic type parsing issues
ChatRun.hits: List["RetrievalHit"] = Relationship(back_populates="run")  # type: ignore
RetrievalHit.run: "ChatRun" = Relationship(back_populates="hits")  # type: ignore
```

## Why This Works

1. **No Forward Reference Issues:** By the time relationships are defined, both classes exist in the namespace
2. **No Generic Type Parsing:** SQLAlchemy can resolve the relationship targets directly
3. **Type Annotations Preserved:** IDE and type checkers still get proper type hints
4. **SQLModel Compatibility:** SQLModel's `Relationship()` works correctly when classes are already defined

## Best Practices

### ✅ DO:

1. **Define relationships after class declarations:**
   ```python
   class Parent(SQLModel, table=True):
       # fields only
   
   class Child(SQLModel, table=True):
       parent_id: int = Field(foreign_key="parent.id")
       # fields only
   
   # Define relationships here
   Parent.children: List["Child"] = Relationship(back_populates="parent")
   Child.parent: "Parent" = Relationship(back_populates="children")
   ```

2. **Use type annotations for IDE support:**
   ```python
   Parent.children: List["Child"] = Relationship(...)  # type: ignore
   ```

3. **Add `# type: ignore` to suppress mypy warnings** about assigning to class attributes

### ❌ DON'T:

1. **Don't define relationships inline with generic types:**
   ```python
   class Parent(SQLModel, table=True):
       children: List["Child"] = Relationship(...)  # ❌ May fail
   ```

2. **Don't use `Mapped` with SQLModel's `Relationship()`:**
   ```python
   hits: Mapped[List["RetrievalHit"]] = Relationship(...)  # ❌ Confuses SQLAlchemy
   ```

3. **Don't omit type annotations entirely:**
   ```python
   hits = Relationship(...)  # ❌ SQLModel requires annotations
   ```

## Alternative Approaches

If you must define relationships inline, consider:

1. **Using `TYPE_CHECKING` for type-only annotations:**
   ```python
   from typing import TYPE_CHECKING
   
   if TYPE_CHECKING:
       from typing import List
   
   class ChatRun(SQLModel, table=True):
       if TYPE_CHECKING:
           hits: List["RetrievalHit"]
       # Define relationship after classes
   ```

2. **Using string-only forward references (less type-safe):**
   ```python
   ChatRun.hits = Relationship(back_populates="run")  # No type annotation
   ```

## Related Issues

- SQLModel GitHub: Issues with relationship type annotations
- SQLAlchemy 2.0: Relationship configuration changes
- Python typing: Forward references with generics

## References

- [SQLModel Documentation](https://sqlmodel.tiangolo.com/)
- [SQLAlchemy Relationships](https://docs.sqlalchemy.org/en/20/orm/relationships.html)
- [Python Type Hints](https://docs.python.org/3/library/typing.html)

## Example from This Project

See `news_assistant/audit_db.py` for the working implementation:

```python
# Lines 78-80
# Define relationships after both classes are declared to avoid forward reference issues
ChatRun.hits: List["RetrievalHit"] = Relationship(back_populates="run")  # type: ignore
RetrievalHit.run: "ChatRun" = Relationship(back_populates="hits")  # type: ignore
```

This pattern ensures:
- ✅ Relationships work correctly
- ✅ Type hints are preserved for IDE support
- ✅ No SQLAlchemy mapper errors
- ✅ Clean, maintainable code
