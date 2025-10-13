from flask_sqlalchemy import SQLAlchemy
db = SQLAlchemy()

class SurveyResponse(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cluster_code = db.Column(db.String(16), index=True, unique=True)

    # meta
    school_type = db.Column(db.String(64))
    program = db.Column(db.String(120))
    discipline = db.Column(db.String(16))
    year_level = db.Column(db.String(8))
    gwa_range = db.Column(db.String(16))

    # tasks (freq/diff)
    grammar_freq = db.Column(db.Integer); grammar_diff = db.Column(db.Integer)
    rephrase_freq = db.Column(db.Integer); rephrase_diff = db.Column(db.Integer)
    summarize_freq = db.Column(db.Integer); summarize_diff = db.Column(db.Integer)
    sources_freq = db.Column(db.Integer);   sources_diff = db.Column(db.Integer)
    brainstorm_freq = db.Column(db.Integer); brainstorm_diff = db.Column(db.Integer)
    outline_freq = db.Column(db.Integer);   outline_diff = db.Column(db.Integer)
    multistep_freq = db.Column(db.Integer); multistep_diff = db.Column(db.Integer)
    complex_freq = db.Column(db.Integer);   complex_diff = db.Column(db.Integer)

    # confidence/productivity
    conf_q1 = db.Column(db.Integer); conf_q2 = db.Column(db.Integer)
    conf_q3 = db.Column(db.Integer); conf_q4 = db.Column(db.Integer)  # reverse-coded source
    conf_q5 = db.Column(db.Integer)
    prod_q1 = db.Column(db.Integer); prod_q2 = db.Column(db.Integer)
    prod_q3 = db.Column(db.Integer); prod_q4 = db.Column(db.Integer)  # reverse-coded source
    prod_q5 = db.Column(db.Integer)

    # crosscheck
    overall_freq = db.Column(db.Integer)
    task_straightforward = db.Column(db.Integer)
    study_effective = db.Column(db.Integer)
    outline_likelihood = db.Column(db.Integer)

    # computed fields
    total_dependency = db.Column(db.Integer)
    total_dependency_pct = db.Column(db.Float)
    possible_overreliance = db.Column(db.Boolean)
    cluster = db.Column(db.String(20))
    conf_mean = db.Column(db.Float)
    prod_mean = db.Column(db.Float)

    @classmethod
    def from_payload(cls, m, r):
        freq = m.get("freq", {}); diff = m.get("difficulty", {})
        conf = m.get("confidence", {}); prod = m.get("productivity", {})
        cross = m.get("cross", {}); meta = m.get("meta", {})
        return cls(
            school_type=meta.get("school_type"), program=meta.get("program"),
            discipline=meta.get("discipline"), year_level=str(meta.get("year_level")),
            gwa_range=meta.get("gwa_range"),
            grammar_freq=freq.get("grammar"), grammar_diff=diff.get("grammar"),
            rephrase_freq=freq.get("rephrase"), rephrase_diff=diff.get("rephrase"),
            summarize_freq=freq.get("summarize"), summarize_diff=diff.get("summarize"),
            sources_freq=freq.get("sources"), sources_diff=diff.get("sources"),
            brainstorm_freq=freq.get("brainstorm"), brainstorm_diff=diff.get("brainstorm"),
            outline_freq=freq.get("outline"), outline_diff=diff.get("outline"),
            multistep_freq=freq.get("multistep"), multistep_diff=diff.get("multistep"),
            complex_freq=freq.get("complex"), complex_diff=diff.get("complex"),
            conf_q1=conf.get("conf_q1"), conf_q2=conf.get("conf_q2"),
            conf_q3=conf.get("conf_q3"), conf_q4=conf.get("conf_q4"),
            conf_q5=conf.get("conf_q5"),
            prod_q1=prod.get("prod_q1"), prod_q2=prod.get("prod_q2"),
            prod_q3=prod.get("prod_q3"), prod_q4=prod.get("prod_q4"),
            prod_q5=prod.get("prod_q5"),
            overall_freq=cross.get("overall_freq"),
            task_straightforward=cross.get("task_straightforward"),
            study_effective=cross.get("study_effective"),
            outline_likelihood=cross.get("outline_likelihood"),
            total_dependency=r.get("total_dependency"),
            total_dependency_pct=r.get("total_dependency_pct"),
            possible_overreliance=r.get("possible_overreliance"),
            cluster=r.get("cluster"),
            conf_mean=r.get("confidence_mean"),
            prod_mean=r.get("productivity_mean"),
            cluster_code=r.get("code"),

        )
