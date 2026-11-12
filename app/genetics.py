"""Pedigree-based kinship (Wright), with unknown founders treated as unrelated."""
from functools import lru_cache


def validate_graph(horses):
    nodes = {h["id"]: h for h in horses}
    visiting, done = set(), set()

    def visit(ident):
        if ident in visiting:
            raise ValueError("El pedigree contiene un ciclo de parentesco.")
        if ident in done:
            return
        if ident not in nodes:
            raise ValueError(f"Falta el registro del progenitor {ident}.")
        visiting.add(ident)
        if len(visiting)>100:
            raise ValueError("El pedigree supera 100 generaciones encadenadas. Revisá los IDs y las relaciones del archivo.")
        h = nodes[ident]
        if h.get("sire_id") and h.get("sire_id") == h.get("dam_id"):
            raise ValueError("Un caballo no puede tener el mismo padre y madre.")
        for key, required_sex in [("sire_id","M"),("dam_id","H")]:
            parent = h.get(key)
            if parent:
                visit(parent)
                p = nodes[parent]
                if p.get("sex", "U") not in (required_sex, "U"):
                    raise ValueError("El sexo de un progenitor no coincide con su relación.")
                if h.get("birth_year") and p.get("birth_year") and p["birth_year"] >= h["birth_year"]:
                    raise ValueError("Un progenitor debe haber nacido antes que su descendiente.")
        visiting.remove(ident)
        done.add(ident)

    for ident in nodes:
        visit(ident)
    return nodes


def pedigree(root_id, nodes, generations=3):
    def branch(ident, depth, path):
        if depth > generations:
            return None
        h = nodes.get(ident)
        if not h:
            return {"id": None,"name": "Sin registrar", "depth": depth,"path":path,
                    "sire": branch(None,depth+1,path+"s"),"dam":branch(None,depth+1,path+"d")}
        return {**h,"depth":depth,"path":path,
                "sire":branch(h.get("sire_id"),depth+1,path+"s"),
                "dam":branch(h.get("dam_id"),depth+1,path+"d")}
    return branch(root_id,0,"")


def analyze(sire_id, dam_id, horses):
    nodes = validate_graph(horses)
    if sire_id not in nodes or dam_id not in nodes:
        raise ValueError("Seleccioná dos caballos registrados.")
    if sire_id == dam_id:
        raise ValueError("Seleccioná dos caballos diferentes.")
    if nodes[sire_id]["sex"] != "M" or nodes[dam_id]["sex"] != "H":
        raise ValueError("El cruce requiere un padrillo y una yegua con sexo registrado.")

    @lru_cache(None)
    def rank(i):
        if not i: return -1
        return 1 + max(rank(nodes[i].get("sire_id")),rank(nodes[i].get("dam_id")))

    @lru_cache(None)
    def kinship(a,b):
        if not a or not b: return 0.0
        if a == b:
            n = nodes[a]
            return (1 + kinship(n.get("sire_id"),n.get("dam_id"))) / 2
        if rank(a) < rank(b): a,b = b,a
        n = nodes[a]
        return (kinship(n.get("sire_id"),b) + kinship(n.get("dam_id"),b)) / 2

    def ancestors(i):
        out, count = {}, 0
        def walk(ident,depth):
            nonlocal count
            if not ident or depth > 3: return
            if depth:
                count += 1
                out.setdefault(ident,set()).add(depth)
            h=nodes[ident]
            walk(h.get("sire_id"),depth+1)
            walk(h.get("dam_id"),depth+1)
        walk(i,0)
        return out,count

    a, ac = ancestors(sire_id)
    b, bc = ancestors(dam_id)
    common = [{"id":i,"name":nodes[i]["name"],"sire_generations":sorted(a[i]),"dam_generations":sorted(b[i])} for i in sorted(a.keys() & b.keys())]
    return {"coefficient":round(kinship(sire_id,dam_id)*100,6), "coverage":round((ac+bc)/28*100,1),
            "known_slots":ac+bc,"total_slots":28,"shared_ancestors":common,
            "method":"Coeficiente de consanguinidad esperado de la cría (Wright). Usa todos los ancestros guardados; cobertura y lista compartida muestran las primeras tres generaciones.",
            "limitations":"Los fundadores sin datos se consideran no emparentados. Un valor bajo con pedigree incompleto puede subestimar la consanguinidad. No es una prueba de ADN ni predice salud, fertilidad o rendimiento. Consultá a un veterinario genetista antes de decidir un cruce."}
